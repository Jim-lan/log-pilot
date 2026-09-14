"""Evaluation integrity against disposable real DuckDB storage."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from shared.evaluation import EvaluationStore


class EvaluationContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["LOGPILOT_TEST_SCRATCH"])
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / 'metrics.duckdb')
        self.store = EvaluationStore(self.path)

    def test_missing_metrics_are_unavailable_and_do_not_create_storage(self):
        self.assertIsNone(self.store.summary()['pass_rate_24h'])
        self.assertFalse(Path(self.path).exists())

    def test_runner_uses_real_context_is_stateless_and_retains_errors(self):
        from unittest.mock import Mock
        from shared.evaluation_runner import run_cases
        cases = [dict(id='a', question='count', expected_sql_result='[(1,)]'),
                 dict(id='b', question='unknown', expected_answer='No evidence')]
        self.store.start('run', ['a', 'b'], {})
        response = Mock()
        response.json.return_value = dict(sql_result='[(1,)]', context='actual source evidence')
        post = Mock(side_effect=[response, RuntimeError('private upstream diagnostics')])
        clock = Mock(side_effect=[10, 12, 20, 24])
        run_cases(self.store, 'run', cases, 'http://fixture.invalid', post, clock)
        self.assertEqual(self.store.summary()['pass_rate_24h'], 50)
        self.assertEqual(self.store.summary()['avg_latency_24h'], 3)
        self.assertFalse(post.call_args.kwargs['json']['persist_history'])
        import duckdb
        with duckdb.connect(self.path, read_only=True) as conn:
            evidence = conn.execute("SELECT evidence FROM evaluation_cases_v1 WHERE case_id='a'").fetchone()[0]
        self.assertIn('actual source evidence', evidence)

    def test_sql_text_and_keywords_alone_do_not_claim_correctness(self):
        from shared.evaluation_runner import score_case
        self.assertEqual(score_case({'expected_keywords': ['good']}, {'answer': 'good'})[0], 'unscored')
        self.assertEqual(score_case({'expected_sql_result': '[(1,)]'}, {'sql_result': '[(2,)]'})[0], 'failed')

    def test_structured_rows_preserve_duplicates_but_allow_unordered_aggregates(self):
        from shared.evaluation_runner import score_case
        case = {'expected_rows': [['ERROR', 2], ['INFO', 1]], 'ordered': False}
        self.assertEqual(score_case(case, {'sql_rows': [['INFO', 1], ['ERROR', 2]]})[0], 'passed')
        self.assertEqual(score_case(case, {'sql_rows': [['ERROR', 2], ['ERROR', 2]]})[0], 'failed')
        self.assertEqual(score_case({'expected_rows': []}, {'sql_rows': []})[0], 'passed')
        self.assertEqual(score_case({'expected_rows': []}, {'sql_rows': None})[0], 'failed')

    def test_retrieval_citation_and_answer_failures_are_distinct(self):
        from shared.evaluation_runner import score_case, score_dimensions
        case = {'expected_answer': 'Restart [source:known]', 'expected_source_ids': ['known'],
                'expected_citation_ids': ['known']}
        response = {'answer': 'Restart [source:known]', 'sources': [{'source_id': 'known'}]}
        self.assertEqual(score_case(case, response)[0], 'passed')
        wrong_answer = {**response, 'answer': 'Delete data [source:known]'}
        self.assertEqual(score_dimensions(case, wrong_answer)['retrieval']['recall'], 1)
        self.assertEqual(score_case(case, wrong_answer)[0], 'failed')
        wrong_source = {**response, 'sources': [{'source_id': 'unrelated'}]}
        self.assertEqual(score_dimensions(case, wrong_source)['retrieval']['recall'], 0)
        self.assertFalse(score_dimensions(case, wrong_source)['citation_validity'])
        self.assertEqual(score_case(case, wrong_source)[0], 'failed')
        no_citation = {**response, 'answer': 'Restart'}
        self.assertEqual(score_dimensions(case, no_citation)['citations']['recall'], 0)

    def test_batch_api_creates_durable_run_without_importing_a_judge(self):
        import importlib.util
        import json
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        source = Path(__file__).resolve().parents[2] / 'services/evaluation_service/src/main.py'
        spec = importlib.util.spec_from_file_location('isolated_evaluation_api', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertFalse(Path(self.path).exists())
        dataset = Path(self.temp.name) / 'cases.json'
        dataset.write_text(json.dumps([dict(id='a', question='fixture', expected_answer='ok')]))
        module.DATASET_PATH, module.METRICS_DB_PATH = str(dataset), self.path
        with patch.object(module, 'run_cases') as run, TestClient(module.app) as client:
            response = client.post('/evaluate/batch', json={})
            self.assertEqual(response.status_code, 200)
            run.assert_called_once()
            self.assertEqual(client.post('/evaluate/batch', json={'dataset_path': '/private/data'}).status_code, 400)
            self.assertEqual(client.post('/evaluate/batch', json={'limit': 0}).status_code, 422)
        self.assertEqual(self.store.summary()['history'][0]['status'], 'running')

    def test_failures_stay_in_denominator_and_latency_is_real(self):
        self.store.start('run', ['a', 'b', 'c'], {'dataset_sha256': 'fixture'})
        self.store.record('run', 'a', 'passed', 2, {'context': 'real evidence'})
        self.store.record('run', 'b', 'failed', 4, {}, 'incorrect_result')
        self.store.record('run', 'c', 'error', 6, {}, 'dependency_error')
        self.store.finish('run')
        result = self.store.summary()
        self.assertEqual(result['pass_rate_24h'], 33.3)
        self.assertEqual(result['avg_latency_24h'], 4)
        self.assertEqual(result['history'][0]['status'], 'completed_with_errors')

    def test_real_window_excludes_old_results_and_weights_cases(self):
        self.store.start('old', ['a'], {}, datetime.utcnow() - timedelta(days=2))
        self.store.record('old', 'a', 'passed', 99, {})
        self.store.finish('old')
        self.store.start('new', ['a'], {})
        self.store.record('new', 'a', 'failed', 2, {})
        self.store.finish('new')
        result = self.store.summary()
        self.assertEqual(result['pass_rate_24h'], 0)
        self.assertEqual(result['avg_latency_24h'], 2)
        self.assertEqual(result['total_runs'], 2)

    def test_interrupted_run_remains_visible_and_pending_cases_are_not_success(self):
        self.store.start('run', ['a', 'b'], {})
        self.store.record('run', 'a', 'passed', 1, {})
        self.assertEqual(self.store.summary()['history'][0]['status'], 'running')
        self.store.finish('run', 'runner_failed')
        result = self.store.summary()
        self.assertEqual(result['pass_rate_24h'], 50)
        self.assertEqual(result['history'][0]['status'], 'failed')
