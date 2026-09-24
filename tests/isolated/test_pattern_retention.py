"""Retention decisions must preserve active and unproven legacy evidence."""
from datetime import datetime, timezone, timedelta
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

from shared.pattern_retention import epoch, pattern_activity, retention_candidate, retention_report


class PatternRetentionContracts(unittest.TestCase):
    def test_active_pattern_preserves_first_seen_but_advances_last_activity(self):
        initial = pattern_activity(None, 10, 20)
        later = pattern_activity(initial, 200, 220)
        self.assertEqual(later['first_seen_at_unix'], 10)
        self.assertEqual(later['last_seen_at_unix'], 200)
        self.assertFalse(retention_candidate({'type': 'log_pattern', **later}, 100))
        late_old_event = pattern_activity(later, 5, 215)
        self.assertEqual(late_old_event['first_seen_at_unix'], 5)
        self.assertEqual(late_old_event['last_seen_at_unix'], 200)
        self.assertEqual(late_old_event['last_indexed_at_unix'], 220)

    def test_replay_and_cutoff_equality_are_retained(self):
        metadata = {'type': 'log_pattern', **pattern_activity(None, 10, 100)}
        self.assertFalse(retention_candidate(metadata, 100))
        self.assertTrue(retention_candidate(metadata, 101))
        replay = {'type': 'log_pattern', **pattern_activity(metadata, 10, 500)}
        self.assertFalse(retention_candidate(replay, 400))
        self.assertFalse(retention_candidate({**metadata, 'type': 'runbook_card'}, 1000))

    def test_unknown_legacy_activity_and_invalid_metadata_fail_closed(self):
        for old in [{}, {'timestamp': 'not-a-date'}, {'retention_schema': 1, 'last_seen_at_unix': float('nan')}]:
            activity = pattern_activity(old, 10, 20)
            self.assertTrue(activity['retention_hold'])
            self.assertFalse(retention_candidate({'type': 'log_pattern', **activity}, 100))
        self.assertFalse(retention_candidate({'type': 'log_pattern', 'timestamp': '1970-01-01'}, 100))
        valid = {'type': 'log_pattern', **pattern_activity(None, 10, 20)}
        for changed in [{'last_seen_at_unix': float('nan')}, {'retention_hold': True}, {'first_seen_at_unix': 100}, {'last_indexed_at_unix': True}]:
            self.assertFalse(retention_candidate({**valid, **changed}, 1000))

    def test_utc_normalization_is_explicit_for_naive_offset_and_z_timestamps(self):
        self.assertEqual(epoch(datetime(1970, 1, 1)), 0)
        self.assertEqual(epoch('1970-01-01T01:00:00+01:00'), 0)
        self.assertEqual(epoch('1970-01-01T00:00:00Z'), 0)
        self.assertEqual(epoch(datetime(1970, 1, 1, 2, tzinfo=timezone(timedelta(hours=2)))), 0)
        for invalid in [True, None, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                epoch(invalid)

    def test_retention_report_is_bounded_and_never_deletes(self):
        collection = Mock()
        collection.count.return_value = 2
        collection.get.return_value = {'ids': ['old', 'active'], 'metadatas': [
            {'type': 'log_pattern', **pattern_activity(None, 10, 20)},
            {'type': 'log_pattern', **pattern_activity(None, 10, 200)}]}
        report = retention_report(collection, 100)
        self.assertEqual(len(report['candidate_id_hashes']), 1)
        self.assertEqual(report['mutations'], 0)
        collection.delete.assert_not_called()
        with self.assertRaises(ValueError):
            retention_report(collection, 100, max_records=1)
        collection.get.return_value['ids'] = ['old', 'old']
        with self.assertRaises(ValueError):
            retention_report(collection, 100)

    def test_janitor_only_requests_a_dry_run_plan(self):
        root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location('retention_janitor', root / 'services/ingestion-worker/src/janitor.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        kb = Mock()
        kb.retention_candidates.return_value = {'mode': 'dry_run', 'mutations': 0}
        self.assertEqual(module.Janitor(kb).run_cleanup()['mutations'], 0)
        kb.delete_older_than.assert_not_called()
        with self.assertRaises(ValueError):
            module.Janitor(kb).run_cleanup(0)
