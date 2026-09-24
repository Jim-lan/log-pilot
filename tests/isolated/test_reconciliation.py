"""Legacy evidence must never become automatic deletion/acknowledgement advice."""
import hashlib
import json
import unittest
from shared.ingestion_reconciliation import reconcile_records


class ReconciliationContracts(unittest.TestCase):
    def test_legacy_mapping_distinguishes_identical_and_conflicting_text(self):
        vectors = [
            {'id': 'old-a', 'document': 'private A', 'metadata': {'service_name': 'fixture', 'cluster_id': 1}},
            {'id': 'old-b', 'document': 'private A', 'metadata': {'service_name': 'fixture', 'cluster_id': 1}},
            {'id': 'old-c', 'document': 'private B', 'metadata': {'service_name': 'fixture', 'cluster_id': 2}},
            {'id': 'old-d', 'document': 'changed B', 'metadata': {'service_name': 'fixture', 'cluster_id': 2}},
        ]
        report = reconcile_records(vectors, [{'fingerprint': 'legacy', 'state': 'failed', 'protocol': 1}], [])
        self.assertEqual({g['status'] for g in report['pattern_groups']}, {'duplicate_text_candidate', 'conflicting_text'})
        self.assertEqual(report['mutations'], 0)
        self.assertTrue(report['claims'][0]['review_required'])
        self.assertTrue(report['review_required'])
        self.assertNotIn('private A', json.dumps(report))
        self.assertNotIn('changed B', json.dumps(report))
        self.assertEqual(report, reconcile_records(list(reversed(vectors)), [{'fingerprint': 'legacy', 'state': 'failed', 'protocol': 1}], []))

    def test_document_gaps_and_unknown_vectors_are_not_guessed(self):
        vectors = [
            {'id': 'card-one', 'document': 'changed', 'metadata': {}},
            {'id': 'card-orphan', 'document': 'unknown', 'metadata': {}},
            {'id': 'legacy-doc', 'document': 'private runbook', 'metadata': {'type': 'runbook_card', 'source': 'secret-file.md'}},
            {'id': 'unclassified', 'document': 'private log', 'metadata': {}},
        ]
        cards = [{'node_id': 'card-one', 'text': 'expected', 'done': True}, {'node_id': 'card-missing', 'text': 'saved', 'done': True}]
        report = reconcile_records(vectors, [], cards)
        self.assertEqual({c['status'] for c in report['document_cards']}, {'missing', 'text_mismatch', 'no_journal'})
        self.assertEqual(len(report['legacy_runbooks']), 1)
        self.assertEqual(len(report['unknown_vectors']), 1)
        self.assertNotIn('secret-file.md', json.dumps(report))
        self.assertNotIn('private', json.dumps(report))

    def test_stable_pattern_mapping_preserves_the_existing_identity_algorithm(self):
        identity = json.dumps(['fixture', '7'])
        stable = 'pattern-' + hashlib.sha256(identity.encode()).hexdigest()
        report = reconcile_records([{'id': stable, 'document': 'pattern', 'metadata': {'service_name': 'fixture', 'cluster_id': 7}}], [], [])
        self.assertEqual(report['pattern_groups'][0]['candidate_id'], stable)
        self.assertEqual(report['pattern_groups'][0]['status'], 'stable')

    def test_incomplete_or_excessive_inventories_fail_instead_of_claiming_completion(self):
        record = {'id': 'fixture', 'document': 'text', 'metadata': {}}
        for vectors, maximum in [([record, record], 100), ([record, {**record, 'id': 'other'}], 1), ([{**record, 'document': None}], 100)]:
            with self.assertRaises(ValueError):
                reconcile_records(vectors, [], [], max_records=maximum)
