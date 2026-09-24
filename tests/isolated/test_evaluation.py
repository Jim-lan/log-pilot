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

    def test_failed_turn_blocks_only_its_conversation_and_keeps_denominator(self):
        from unittest.mock import Mock
        from shared.evaluation_runner import run_cases
        cases = [dict(id='a1', question='fail', conversation_id='a', turn_index=1, expected_answer='ok'),
                 dict(id='a2', question='followup', conversation_id='a', turn_index=2, expected_answer='ok'),
                 dict(id='b1', question='independent', conversation_id='b', turn_index=1, expected_answer='ok')]
        self.store.start('run', [c['id'] for c in cases], {})
        response = Mock()
        response.json.return_value = {'answer': 'ok'}
        post = Mock(side_effect=[RuntimeError('offline'), response])
        run_cases(self.store, 'run', cases, 'http://fixture', post=post)
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args.kwargs['json']['evaluation_context'], [])
        self.assertEqual(self.store.summary()['pass_rate_24h'], 33.3)
        import duckdb
        with duckdb.connect(self.path, read_only=True) as conn:
            self.assertEqual(conn.execute("SELECT status, latency, failure_code FROM evaluation_cases_v1 WHERE case_id='a2'").fetchone(),
                             ('error', None, 'prior_turn_failed'))

    def test_context_rolls_complete_pairs_and_never_uses_expected_answer(self):
        from unittest.mock import Mock
        from shared.evaluation_runner import run_cases
        cases = [dict(id=str(i), question='q' + str(i), conversation_id='a', turn_index=i + 1,
                      expected_answer='secret expected answer') for i in range(7)]
        response = Mock()
        response.json.return_value = {'answer': 'actual answer'}
        post, store = Mock(return_value=response), Mock()
        run_cases(store, 'run', cases, 'http://fixture', post=post)
        context = post.call_args.kwargs['json']['evaluation_context']
        self.assertEqual(len(context), 10)
        self.assertEqual(context[0]['content'], 'q1')
        self.assertEqual(context[-1]['content'], 'actual answer')
        self.assertNotIn('secret expected answer', str(post.call_args_list))

    def test_oversized_answer_blocks_followup_instead_of_silently_truncating(self):
        from unittest.mock import Mock
        from shared.evaluation_runner import run_cases
        cases = [dict(id=str(i), question='q', conversation_id='c', turn_index=i + 1,
                      expected_answer='ok') for i in range(2)]
        response, store = Mock(), Mock()
        response.json.return_value = {'answer': 'x' * 16001}
        post = Mock(return_value=response)
        run_cases(store, 'run', cases, 'http://fixture', post=post)
        post.assert_called_once()
        self.assertEqual(store.record.call_args_list[0].args[2], 'error')
        self.assertEqual(store.record.call_args_list[1].args[-1], 'prior_turn_failed')

    def test_dataset_rejects_broken_turn_sequences_and_duplicate_cases(self):
        from shared.evaluation_context import validate_cases
        first = dict(id='a', question='q', conversation_id='c', turn_index=1)
        invalid = [[{**first, 'turn_index': 2}], [{**first, 'turn_index': True}],
                   [{**first, 'conversation_id': None}], [first, first],
                   [dict(id='a', question='q', turn_index=1)],
                   [first, {**first, 'id': 'b', 'turn_index': 3}]]
        for cases in invalid:
            with self.assertRaises(ValueError):
                validate_cases(cases)

    def test_versioned_holdout_sources_and_negative_controls(self):
        import json
        from shared.evaluation_dataset import load_dataset
        from shared.evaluation_runner import score_case
        value = json.loads((Path(__file__).parent / 'quality_holdout_v2.json').read_text())
        cases, provenance = load_dataset(value)
        self.assertEqual(provenance['dataset_split'], 'held_out')
        self.assertEqual(provenance['dataset_version'], '2.0.0')
        development = json.loads((Path(__file__).parent / 'quality_cases_v1.json').read_text())
        self.assertFalse({c['id'] for c in cases} & {c['id'] for c in development['cases']})
        facts = {f['fact_id']: f for f in value['source_facts']}
        for case in cases:
            if 'expected_answer' not in case:
                continue
            self.assertEqual({facts[f]['source_id'] for f in case['fact_ids']}, set(case['expected_source_ids']))
            response = dict(answer=case['expected_answer'], sources=[{'source_id': x} for x in case['expected_source_ids']],
                            metadata={'outcome': case['expected_outcome']})
            self.assertEqual(score_case(case, response)[0], 'passed')
            self.assertEqual(score_case(case, {**response, 'answer': 'Fabricated fact [source:invented]'})[0], 'failed')
            self.assertEqual(score_case(case, {**response, 'metadata': {'outcome': 'dependency_error'}})[0], 'failed')
            if case['expected_source_ids']:
                self.assertEqual(score_case(case, {**response, 'sources': [{'source_id': 'unrelated'}]})[0], 'failed')
                self.assertEqual(score_case(case, {**response, 'answer': 'Wrong fact [source:' + case['expected_source_ids'][0] + ']'})[0], 'failed')

    def test_dataset_envelope_validation_preserves_legacy_compatibility(self):
        from shared.evaluation_dataset import load_dataset
        cases = [dict(id='a', question='q', expected_answer='ok')]
        self.assertEqual(load_dataset(cases)[1]['dataset_split'], 'legacy_unpartitioned')
        valid = dict(schema_version=2, dataset_id='fixture', version='1', split='held_out', cases=cases)
        for field, value in [('schema_version', True), ('version', ''), ('dataset_id', None), ('split', 'unknown')]:
            with self.assertRaises(ValueError):
                load_dataset({**valid, field: value})

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
            dataset.write_text(json.dumps(dict(schema_version=2, dataset_id='fixture', version='2.0.0',
                                               split='held_out', cases=[dict(id='b', question='q', expected_answer='ok')])))
            envelope_response = client.post('/evaluate/batch', json={})
            self.assertEqual(envelope_response.status_code, 200)
            import duckdb
            with duckdb.connect(self.path, read_only=True) as conn:
                provenance = json.loads(conn.execute('SELECT provenance FROM evaluation_runs_v1 WHERE run_id=?',
                                                     [envelope_response.json()['run_id']]).fetchone()[0])
            self.assertEqual(provenance['dataset_split'], 'held_out')
            self.assertEqual(provenance['dataset_version'], '2.0.0')
            import hashlib
            self.assertEqual(provenance['dataset_sha256'], hashlib.sha256(dataset.read_bytes()).hexdigest())
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
