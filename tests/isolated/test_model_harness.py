"""Offline model controls and comparison integrity with real storage/HTTP contracts."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import duckdb
from shared.model_profiles import ProfileCatalog
from shared.model_comparison import ComparisonRequest, plan_comparison, run_comparison, comparison_report
from shared.evaluation import EvaluationStore
from shared.evaluation_runner import run_cases


def catalog_value():
    return {'schema_version': 1, 'api_base': 'http://fixture.invalid/v1', 'profiles': {
        name: {'generation': {'model': model}, 'validation': {'model': 'fixed-judge'}}
        for name, model in [('small', 'fixture:4b'), ('large', 'fixture:9b')]}}


class ModelHarnessContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ['LOGPILOT_TEST_SCRATCH'])
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / 'metrics.duckdb')
        self.store = EvaluationStore(self.path)
        self.catalog = ProfileCatalog.model_validate(catalog_value())
        self.cases = [{'id': 'one', 'question': 'q', 'expected_answer': 'correct'}]
        self.request = ComparisonRequest(profiles=['small', 'large'], repeats=2, data_revision='frozen-fixture',
                                         min_pass_rate=1, max_error_rate=0, max_p95_seconds=5)
        self.id, self.runs = plan_comparison(self.request, self.catalog, self.cases, {'dataset_sha256': 'fixture'})

    def evidence(self, provenance):
        profile = provenance['model_profile']
        settings = profile['generation']
        return {'answer': 'correct', 'metadata': {'outcome': 'validated', 'request_id': 'fixture', 'provenance': {
            'model_profile': profile, 'evaluation_data_revision': 'frozen-fixture',
            'templates': {'answer.j2': 'a' * 64}, 'model_calls': [{'role': 'generation',
                'requested_model': settings['model'], 'returned_model': settings['model'],
                'settings': {k: v for k, v in settings.items() if k != 'model' and v is not None},
                'usage': {'total_tokens': 12}}]}}}

    def complete(self):
        self.store.start_many(self.runs)
        for run_id, _, provenance in self.runs:
            name = provenance['model_profile']['profile_id']
            self.store.record(run_id, 'one', 'passed' if name == 'small' else 'failed', 1 if name == 'small' else 2,
                              self.evidence(provenance))
            self.store.finish(run_id)

    def test_catalog_validation_hash_pinning_and_immutability(self):
        profile, manifest = self.catalog.resolve('small')
        self.assertEqual(manifest, self.catalog.resolve('small')[1])
        with self.assertRaises(ValueError):
            profile.generation.temperature = .5
        changed = catalog_value()
        changed['profiles']['small']['generation']['temperature'] = .5
        self.assertNotEqual(manifest['profile_sha256'], ProfileCatalog.model_validate(changed).resolve('small')[1]['profile_sha256'])
        for field, value in [('temperature', float('nan')), ('max_tokens', 0), ('seed', True), ('url', 'https://untrusted')]:
            invalid = catalog_value()
            invalid['profiles']['small']['generation'][field] = value
            with self.assertRaises(ValueError):
                ProfileCatalog.model_validate(invalid)
        with self.assertRaises(ValueError):
            self.catalog.resolve('unknown')

    def test_fixed_validator_and_bounded_plan_rotate_candidate_order(self):
        self.assertEqual([p['model_profile']['profile_id'] for _, _, p in self.runs], ['small', 'large', 'large', 'small'])
        invalid = catalog_value()
        invalid['profiles']['large']['validation']['model'] = 'different-judge'
        with self.assertRaises(ValueError):
            plan_comparison(self.request, ProfileCatalog.model_validate(invalid), self.cases, {})
        with self.assertRaises(ValueError):
            ComparisonRequest(profiles=['small', 'small'], data_revision='f')
        with self.assertRaises(ValueError):
            plan_comparison(self.request.model_copy(update={'repeats': 5}), self.catalog, self.cases * 1000, {})

    def test_comparison_roster_is_atomic(self):
        self.store.start('existing', ['one'], {})
        with self.assertRaises(duckdb.Error):
            self.store.start_many([self.runs[0], ('existing', ['other'], {})])
        self.assertEqual(self.store.summary()['total_runs'], 1)

    def test_report_separates_judge_acceptance_correctness_usage_and_decision(self):
        self.complete()
        report = comparison_report(self.path, self.id)
        self.assertTrue(report['complete'])
        self.assertEqual(report['recommendation'], 'small')
        small, large = report['candidates']
        self.assertEqual(small['total_cases'], 2)
        self.assertEqual(small['total_tokens'], 24)
        self.assertEqual(large['runtime_validated_rate'], 1)
        self.assertEqual(large['pass_rate'], 0)
        self.assertIsNone(small['cost'])

    def test_pending_and_interrupted_runs_never_recommend(self):
        self.store.start_many(self.runs)
        self.assertEqual(comparison_report(self.path, self.id)['decision'], 'incomplete')
        self.store.interrupt_running()
        self.assertIsNone(comparison_report(self.path, self.id)['recommendation'])
        self.assertEqual(comparison_report(self.path, self.id)['candidates'][0]['error_rate'], 1)

    def test_template_drift_and_missing_thresholds_block_recommendation(self):
        self.complete()
        with duckdb.connect(self.path) as conn:
            evidence = self.evidence(self.runs[0][2])
            evidence['metadata']['provenance']['templates']['answer.j2'] = 'b' * 64
            conn.execute('UPDATE evaluation_cases_v1 SET evidence=? WHERE run_id=?', [json.dumps(evidence), self.runs[0][0]])
        report = comparison_report(self.path, self.id)
        self.assertEqual(report['decision'], 'provenance_changed')
        self.assertIsNone(report['recommendation'])
        request = ComparisonRequest(profiles=['small', 'large'], repeats=1, data_revision='frozen-fixture')
        comparison_id, runs = plan_comparison(request, self.catalog, self.cases, {})
        self.store.start_many(runs)
        for run_id, _, provenance in runs:
            self.store.record(run_id, 'one', 'passed', 1, self.evidence(provenance))
            self.store.finish(run_id)
        self.assertEqual(comparison_report(self.path, comparison_id)['decision'], 'gates_not_set')

    def test_runner_pins_profile_and_rejects_silent_fallback(self):
        self.store.start_many(self.runs)
        response = Mock()
        response.json.return_value = {'answer': 'correct', 'metadata': {}}
        post = Mock(return_value=response)
        run_id, _, provenance = self.runs[0]
        run_cases(self.store, run_id, self.cases, 'http://fixture', post=post, model_profile='small',
                  expected_profile_sha256=provenance['model_profile']['profile_sha256'], data_revision='frozen-fixture')
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['model_profile'], 'small')
        self.assertFalse(payload['persist_history'])
        self.assertNotIn('expected_answer', payload)
        with duckdb.connect(self.path, read_only=True) as conn:
            self.assertEqual(conn.execute('SELECT status FROM evaluation_cases_v1 WHERE run_id=?', [run_id]).fetchone()[0], 'error')

    def test_comparison_runner_uses_independent_runs_and_keeps_unstarted_errors(self):
        self.store.start_many(self.runs)
        runner = Mock(side_effect=RuntimeError('injected failure'))
        with self.assertRaises(RuntimeError):
            run_comparison(self.store, self.runs, self.cases, 'http://fixture', runner=runner)
        self.assertEqual(self.store.summary()['case_counts_24h']['error'], 4)
        self.assertIsNone(comparison_report(self.path, self.id)['recommendation'])

    def test_comparison_api_persists_roster_and_serves_report(self):
        import importlib.util
        from fastapi.testclient import TestClient
        root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location('comparison_api', root / 'services/evaluation_service/src/main.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.METRICS_DB_PATH = self.path
        dataset = Path(self.temp.name) / 'cases.json'
        dataset.write_text(json.dumps(self.cases))
        module.DATASET_PATH = str(dataset)
        profiles = Path(self.temp.name) / 'profiles.json'
        profiles.write_text(json.dumps(catalog_value()))
        with patch.dict(os.environ, {'LOGPILOT_MODEL_PROFILES_PATH': str(profiles)}), patch.object(module, 'run_comparison') as run:
            with TestClient(module.app) as client:
                response = client.post('/evaluate/compare', json=self.request.model_dump())
                self.assertEqual(response.status_code, 200, response.text)
                run.assert_called_once()
                comparison_id = response.json()['comparison_id']
                report = client.get('/evaluate/comparisons/' + comparison_id).json()
                self.assertEqual(len(report['runs']), 4)
                self.assertEqual(report['decision'], 'incomplete')
                module.evaluation_job.acquire()
                try:
                    self.assertEqual(client.post('/evaluate/compare', json=self.request.model_dump()).status_code, 409)
                finally:
                    module.evaluation_job.release()

    def test_report_ties_and_unknown_usage_do_not_invent_winner_or_cost(self):
        self.store.start_many(self.runs)
        for run_id, _, provenance in self.runs:
            evidence = self.evidence(provenance)
            evidence['metadata']['provenance']['model_calls'][0]['usage'] = None
            self.store.record(run_id, 'one', 'passed', 1, evidence)
            self.store.finish(run_id)
        report = comparison_report(self.path, self.id)
        self.assertEqual(report['decision'], 'tie')
        self.assertIsNone(report['recommendation'])
        self.assertTrue(all(c['total_tokens'] is None for c in report['candidates']))

    def test_report_rejects_observed_model_settings_different_from_profile(self):
        self.complete()
        with duckdb.connect(self.path) as conn:
            for run_id, _, provenance in self.runs:
                evidence = self.evidence(provenance)
                evidence['metadata']['provenance']['model_calls'][0]['settings']['temperature'] = 2
                conn.execute('UPDATE evaluation_cases_v1 SET evidence=? WHERE run_id=?', [json.dumps(evidence), run_id])
        report = comparison_report(self.path, self.id)
        self.assertIsNone(report['recommendation'])
        self.assertTrue(all(not c['provenance_verified'] for c in report['candidates']))

    def test_cli_saves_report_and_refuses_overwrite_before_starting_work(self):
        import importlib.util
        import contextlib
        import io
        import sys
        root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location('comparison_cli', root / 'scripts/compare_models.py')
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        output = Path(self.temp.name) / 'report.json'
        response = Mock()
        response.json.return_value = {'comparison_id': self.id, 'decision': 'incomplete'}
        args = ['compare_models', '--comparison-id', self.id, '--output', str(output)]
        with patch.object(sys, 'argv', args), patch.object(cli.requests, 'get', return_value=response) as get:
            with contextlib.redirect_stdout(io.StringIO()):
                cli.main()
            self.assertEqual(json.loads(output.read_text())['comparison_id'], self.id)
            get.assert_called_once()
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                cli.main()
            get.assert_called_once()

    def test_end_to_end_comparison_runner_isolates_conversations_between_profiles_and_repeats(self):
        cases = [dict(id='one', question='first', expected_answer='correct', conversation_id='c', turn_index=1),
                 dict(id='two', question='next', expected_answer='correct', conversation_id='c', turn_index=2)]
        comparison_id, runs = plan_comparison(self.request, self.catalog, cases, {'dataset_sha256': 'fixture'})
        self.store.start_many(runs)
        observed = []
        def post(url, json, timeout):
            observed.append(json)
            response = Mock()
            _, manifest = self.catalog.resolve(json['model_profile'])
            response.json.return_value = self.evidence({'model_profile': manifest})
            return response
        def runner(*args, **kwargs):
            run_cases(*args, post=post, **kwargs)
        run_comparison(self.store, runs, cases, 'http://fixture', runner=runner)
        self.assertEqual(len(observed), 8)
        for i, payload in enumerate(observed):
            self.assertEqual(len(payload['evaluation_context']), 0 if i % 2 == 0 else 2)
        report = comparison_report(self.path, comparison_id)
        self.assertTrue(report['complete'])
        self.assertEqual([c['pass_rate'] for c in report['candidates']], [1, 1])

    def test_correct_rows_with_unexpected_abstention_are_not_comparison_success(self):
        case = {'id': 'rows', 'question': 'count', 'expected_rows': [[1]]}
        run_id, _, provenance = self.runs[0]
        self.store.start(run_id, ['rows'], provenance)
        response = Mock()
        evidence = self.evidence(provenance)
        evidence['sql_rows'] = [[1]]
        evidence['metadata']['outcome'] = 'insufficient_evidence'
        response.json.return_value = evidence
        run_cases(self.store, run_id, [case], 'http://fixture', post=Mock(return_value=response),
                  model_profile='small', expected_profile_sha256=provenance['model_profile']['profile_sha256'],
                  data_revision='frozen-fixture')
        with duckdb.connect(self.path, read_only=True) as conn:
            self.assertEqual(conn.execute('SELECT status,failure_code FROM evaluation_cases_v1').fetchone(),
                             ('failed', 'unexpected_outcome'))
