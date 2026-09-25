"""Reviewed claim fixtures test support separately from valid citation IDs."""
import hashlib
import unittest
from types import SimpleNamespace

from shared.evidence import source_record, web_evidence
from shared.evaluation_context import validate_cases
from shared.evaluation_runner import score_case, score_dimensions


class CitationContracts(unittest.TestCase):
    def setUp(self):
        self.digest = hashlib.sha256(b'Retry limit: three.').hexdigest()
        self.claim = {'text': 'The retry limit is three.', 'supports': [
            {'source_id': 'queue', 'content_sha256': self.digest}]}
        self.case = {'id': 'retry', 'question': 'Retry limit?',
                     'expected_answer': 'The retry limit is three. [source:queue]',
                     'citation_claims': [self.claim]}
        self.response = {'answer': self.case['expected_answer'], 'sources': [
            {'source_id': 'queue', 'content_sha256': self.digest}]}

    def test_reviewed_claim_support_and_coverage_pass(self):
        validate_cases([self.case])
        scores = score_dimensions(self.case, self.response)
        self.assertEqual(scores['citation_coverage'], 1)
        self.assertEqual(scores['citation_support'], 1)
        self.assertEqual(score_case(self.case, self.response)[0], 'passed')

    def test_valid_id_does_not_support_wrong_claim_or_stale_artifact(self):
        variants = [{**self.response, 'answer': 'The retry limit is unlimited. [source:queue]'},
                    {**self.response, 'sources': [{'source_id': 'queue', 'content_sha256': '0' * 64}]},
                    {**self.response, 'sources': self.response['sources'] * 2}]
        for response in variants:
            scores = score_dimensions(self.case, response)
            self.assertTrue(scores['citation_validity'])
            self.assertEqual(scores['citation_support'], 0)
            # Even making the output exact cannot bypass the reviewed support check.
            case = {**self.case, 'expected_answer': response['answer']}
            self.assertEqual(score_case(case, response)[0], 'failed')

    def test_missing_partial_and_unexpected_claims_have_honest_denominators(self):
        second = {'text': 'Wait 45 seconds.', 'supports': self.claim['supports']}
        case = {**self.case, 'citation_claims': [self.claim, second]}
        self.assertEqual(score_dimensions(case, self.response)['citation_coverage'], .5)
        for answer in ['The retry limit is three.', '', '[source:queue]']:
            scores = score_dimensions(self.case, {**self.response, 'answer': answer})
            self.assertEqual(scores['citation_coverage'], 0)
            self.assertEqual(scores['citation_support'], 0)
        answer = self.response['answer'] + '\nDangerous advice. [source:queue]'
        scores = score_dimensions(self.case, {**self.response, 'answer': answer})
        self.assertEqual(scores['citation_coverage'], .5)
        self.assertEqual(scores['citation_support'], .5)
        duplicate = self.response['answer'] + '\n' + self.response['answer']
        self.assertEqual(score_dimensions(self.case, {**self.response, 'answer': duplicate})['citation_support'], .5)

    def test_unrelated_valid_citation_is_penalized_even_beside_supported_one(self):
        response = {'answer': self.response['answer'] + ' [source:other]',
                    'sources': self.response['sources'] + [{'source_id': 'other', 'content_sha256': self.digest}]}
        scores = score_dimensions(self.case, response)
        self.assertTrue(scores['citation_validity'])
        self.assertEqual(scores['citation_coverage'], 1)
        self.assertEqual(scores['citation_support'], .5)

    def test_unreviewed_claims_are_unscored_not_implicitly_supported(self):
        scores = score_dimensions({}, self.response)
        self.assertIsNone(scores['citation_coverage'])
        self.assertIsNone(scores['citation_support'])
        self.assertIsNone(scores['web_attribution'])

    def test_invalid_claim_contracts_rejected_before_run(self):
        for claims in [[], None, [self.claim, self.claim], [{'text': 'x', 'supports': []}],
                       [{**self.claim, 'text': 'first\nsecond'}],
                       [{**self.claim, 'supports': [{'source_id': 'queue', 'content_sha256': 'bad'}]}]]:
            with self.assertRaises(ValueError):
                validate_cases([{**self.case, 'citation_claims': claims}])

    def test_web_snippets_have_stable_content_bound_ids_and_safe_urls(self):
        item = {'href': 'https://fixture.invalid/runbook', 'title': 'Runbook', 'body': 'Retry limit: three.'}
        evidence = web_evidence([item, item])
        self.assertEqual(len(evidence['sources']), 1)
        source = evidence['sources'][0]
        self.assertEqual(source['content_sha256'], self.digest)
        self.assertIn('[source:' + source['source_id'] + ']', evidence['context'])
        self.assertEqual(web_evidence([item])['sources'][0]['source_id'], source['source_id'])
        for change in [{'body': 'Changed'}, {'href': 'https://fixture.invalid/other'}]:
            self.assertNotEqual(web_evidence([{**item, **change}])['sources'][0]['source_id'], source['source_id'])
        for url in ['javascript:alert(1)', 'file:///tmp/private', 'https://user:secret@fixture.invalid',
                    'https://fixture.invalid:bad', 'https://fixture.invalid/\nsecret', None]:
            self.assertEqual(web_evidence([{**item, 'href': url}])['sources'], [])
        self.assertEqual(web_evidence([{**item, 'body': ''}, None])['sources'], [])

    def test_web_attribution_and_support_are_independent(self):
        source = web_evidence([{'href': 'https://fixture.invalid', 'body': 'Retry limit: three.'}])['sources'][0]
        answer = 'The retry limit is three. [source:' + source['source_id'] + ']'
        case = {**self.case, 'expected_answer': answer, 'citation_claims': [
            {**self.claim, 'supports': [{'source_id': source['source_id'], 'content_sha256': self.digest}]}]}
        response = {'answer': answer, 'sources': [source]}
        self.assertEqual(score_case(case, response)[0], 'passed')
        for mutation in [{'url': 'javascript:alert(1)'}, {'retrieved_at': 'invalid'},
                         {'retrieved_at': '2026-09-25T12:00:00'}, {'provenance': 'full_page'}]:
            changed = {**response, 'sources': [{**source, **mutation}]}
            self.assertEqual(score_dimensions(case, changed)['web_attribution'], 0)
            self.assertEqual(score_case(case, changed)[0], 'failed')
        changed = {**response, 'answer': 'Invented advice. [source:' + source['source_id'] + ']'}
        self.assertEqual(score_dimensions(case, changed)['web_attribution'], 1)
        self.assertEqual(score_dimensions(case, changed)['citation_support'], 0)

    def test_runner_persists_dimensions_without_sending_expected_claims(self):
        import json
        import os
        import tempfile
        from pathlib import Path
        from unittest.mock import Mock
        import duckdb
        from shared.evaluation import EvaluationStore
        from shared.evaluation_runner import run_cases
        with tempfile.TemporaryDirectory(dir=os.environ['LOGPILOT_TEST_SCRATCH']) as scratch:
            path = str(Path(scratch) / 'metrics.duckdb')
            store = EvaluationStore(path)
            store.start('run', [self.case['id']], {})
            response = Mock()
            response.json.return_value = self.response
            post = Mock(return_value=response)
            run_cases(store, 'run', [self.case], 'http://fixture', post=post)
            self.assertEqual(post.call_args.kwargs['json'],
                             {'query': self.case['question'], 'persist_history': False})
            with duckdb.connect(path, read_only=True) as conn:
                status, evidence = conn.execute('SELECT status,evidence FROM evaluation_cases_v1').fetchone()
            self.assertEqual(status, 'passed')
            self.assertEqual(json.loads(evidence)['dimensions']['citation_support'], 1)

    def test_document_origin_retained_without_conflating_artifact_and_original(self):
        metadata = dict(type='runbook_card', source_id='original', version_id='immutable',
                        source_spans='[{"start_byte":0,"end_byte":42}]', span_scope='whole_document_input')
        record = source_record(SimpleNamespace(node_id='card', metadata=metadata), 'derived card')
        self.assertNotEqual(record['source_id'], 'original')
        self.assertEqual(record['document_origin']['source_id'], 'original')
        self.assertEqual(record['document_origin']['span_scope'], 'whole_document_input')
        self.assertEqual(record['provenance'], 'retrieved_artifact')
