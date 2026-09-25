"""Recovery and provenance on disposable evaluation stores only."""
import json
import os
from pathlib import Path
import tempfile
import unittest
import duckdb
from shared.evaluation import EvaluationStore
from shared.evaluation_owner import evaluation_owner
from shared.evaluation_provenance import scorer_identity


class EvaluationRecoveryContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ['LOGPILOT_TEST_SCRATCH'])
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / 'metrics.duckdb')
        self.store = EvaluationStore(self.path)

    def test_recovery_preserves_results_and_is_idempotent(self):
        provenance = {**scorer_identity(), 'dataset_sha256': 'fixture'}
        self.store.start('run', ['done', 'pending'], provenance)
        evidence = {'answer': 'actual answer', 'metadata': {'provenance': {
            'model_calls': [{'requested_model': 'fixture', 'returned_model': 'fixture-v1',
                             'temperature': .2, 'system_fingerprint': None, 'outcome': 'completed'}],
            'templates': {'answer.j2': 'a' * 64}}}}
        self.store.record('run', 'done', 'passed', 2, evidence)
        with evaluation_owner(self.path):
            self.assertEqual(self.store.interrupt_running(), 1)
            self.assertEqual(self.store.interrupt_running(), 0)
        with duckdb.connect(self.path, read_only=True) as conn:
            rows = conn.execute('SELECT case_id,status,latency,evidence,failure_code FROM evaluation_cases_v1 ORDER BY case_id').fetchall()
            status, raw = conn.execute('SELECT status,provenance FROM evaluation_runs_v1').fetchone()
        self.assertEqual(rows[0], ('done', 'passed', 2, json.dumps(evidence), None))
        self.assertEqual(rows[1], ('pending', 'error', None, None, 'interrupted'))
        self.assertEqual(status, 'interrupted')
        recorded = json.loads(raw)
        self.assertEqual(recorded['scorer_sha256'], provenance['scorer_sha256'])
        self.assertEqual(recorded['execution']['coverage'], 'partial')
        self.assertEqual(recorded['execution']['missing_case_ids'], ['pending'])
        self.assertEqual(recorded['execution']['models'][0]['returned_model'], 'fixture-v1')
        self.assertEqual(recorded['execution']['templates'], {'answer.j2': ['a' * 64]})
        summary = self.store.summary()
        self.assertEqual(summary['pass_rate_24h'], 50)
        self.assertEqual(summary['total_cases_24h'], 2)
        self.assertEqual(summary['case_counts_24h']['error'], 1)
        self.assertEqual(sum(summary['case_counts_24h'].values()), 2)
        self.assertEqual(summary['history'][0]['total_cases'], 2)
        with self.assertRaises(ValueError):
            self.store.record('run', 'pending', 'passed', 1, {})
        self.store.finish('run')
        self.assertEqual(self.store.summary()['history'][0]['status'], 'interrupted')

    def test_live_owner_cannot_be_replaced_and_lock_releases(self):
        self.store.start('live', ['one'], {})
        with evaluation_owner(self.path):
            with self.assertRaises(RuntimeError), evaluation_owner(self.path):
                self.fail('second owner admitted')
            self.assertEqual(self.store.summary()['history'][0]['status'], 'running')
        with evaluation_owner(self.path):
            self.assertEqual(self.store.interrupt_running(), 1)

    def test_recovery_does_not_create_database_or_touch_finished_runs(self):
        with evaluation_owner(self.path):
            self.assertEqual(self.store.interrupt_running(), 0)
        self.assertFalse(Path(self.path).exists())
        self.assertIsNone(self.store.summary()['case_counts_24h'])
        self.store.start('done', ['one'], {})
        self.store.record('done', 'one', 'passed', 1, {})
        self.store.finish('done')
        with evaluation_owner(self.path):
            self.assertEqual(self.store.interrupt_running(), 0)
        self.store.finish('done', 'late_error')
        self.assertEqual(self.store.summary()['history'][0]['status'], 'completed')

    def test_scorer_identity_is_stable_and_bound_to_actual_files(self):
        import hashlib
        from shared import evaluation_provenance
        identity = scorer_identity()
        self.assertEqual(identity, scorer_identity())
        for name, digest in identity['scorer_files'].items():
            path = Path(evaluation_provenance.__file__).parent / name
            self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(identity['contract_version'], 4)

    def test_startup_recovers_before_accepting_new_work(self):
        import importlib.util
        from fastapi.testclient import TestClient
        self.store.start('abandoned', ['one'], {})
        root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location('recovery_api', root / 'services/evaluation_service/src/main.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.METRICS_DB_PATH = self.path
        with TestClient(module.app) as client:
            self.assertEqual(client.get('/health').status_code, 200)
            self.assertEqual(self.store.summary()['history'][0]['status'], 'interrupted')
            with self.assertRaises(RuntimeError), evaluation_owner(self.path):
                pass
        with evaluation_owner(self.path):
            self.assertEqual(self.store.interrupt_running(), 0)

    def test_status_counts_include_pending_unscored_and_failures(self):
        self.store.start('mixed', ['a', 'b', 'c', 'd', 'e'], {})
        for case_id, status in zip(['a', 'b', 'c', 'd'], ['passed', 'failed', 'error', 'unscored']):
            self.store.record('mixed', case_id, status, 1, {})
        summary = self.store.summary()
        self.assertEqual(summary['case_counts_24h'], dict.fromkeys(['passed', 'failed', 'error', 'unscored', 'pending'], 1))
        self.assertEqual(summary['pass_rate_24h'], 20)
        self.assertEqual(summary['total_cases_24h'], 5)

    def test_recovery_transaction_rolls_back_on_aggregation_failure(self):
        from unittest.mock import patch
        self.store.start('run', ['one'], {})
        with evaluation_owner(self.path):
            with patch.object(self.store, '_aggregate_provenance', side_effect=RuntimeError('injected failure')):
                with self.assertRaises(RuntimeError):
                    self.store.interrupt_running()
            summary = self.store.summary()
            self.assertEqual(summary['history'][0]['status'], 'running')
            self.assertEqual(summary['case_counts_24h']['pending'], 1)
            self.assertEqual(self.store.interrupt_running(), 1)

    def test_finalization_retains_multiple_actual_model_and_template_versions(self):
        self.store.start('run', ['a', 'b'], scorer_identity())
        for case_id, digest in [('a', 'a' * 64), ('b', 'b' * 64)]:
            self.store.record('run', case_id, 'passed', 1, {'metadata': {'provenance': {
                'model_calls': [{'requested_model': 'alias', 'returned_model': case_id,
                                 'temperature': 0, 'outcome': 'completed'}],
                'templates': {'answer.j2': digest}}}})
        self.store.finish('run')
        with duckdb.connect(self.path, read_only=True) as conn:
            provenance = json.loads(conn.execute('SELECT provenance FROM evaluation_runs_v1').fetchone()[0])
        execution = provenance['execution']
        self.assertEqual(execution['coverage'], 'complete')
        self.assertEqual({m['returned_model'] for m in execution['models']}, {'a', 'b'})
        self.assertEqual(execution['templates']['answer.j2'], ['a' * 64, 'b' * 64])

    def test_failure_provenance_snapshot_is_detached_from_late_worker_updates(self):
        from shared.execution import RequestBudget
        budget = RequestBudget(30, 2)
        budget.provenance['model_calls'].append({'requested_model': 'fixture', 'returned_model': None})
        snapshot = budget.provenance_snapshot()
        budget.provenance['model_calls'][0]['returned_model'] = 'late model'
        self.assertIsNone(snapshot['model_calls'][0]['returned_model'])
