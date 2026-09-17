import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import Mock, patch
from datetime import datetime

from shared.ingestion_ledger import IngestionLedger
from shared.db.duckdb_client import DuckDBConnector
from shared.log_schema import LogEvent

ROOT = Path(__file__).resolve().parents[2]


class IngestionContracts(unittest.TestCase):
    def setUp(self):
        previous = Path.cwd()
        tmp = tempfile.TemporaryDirectory(dir=os.environ['LOGPILOT_TEST_SCRATCH'])
        self.addCleanup(tmp.cleanup)
        self.addCleanup(os.chdir, previous)
        os.chdir(tmp.name)
        modules = {}
        for name, attr in [('services.knowledge_base.src.store', 'KnowledgeStore'),
                           ('shared.llm.client', 'LLMClient'), ('llama_index.core', 'Document'),
                           ('shared.utils.template_miner', 'LogTemplateMiner'), ('janitor', 'Janitor'),
                           ('watchdog.observers', 'Observer'), ('watchdog.events', 'FileSystemEventHandler')]:
            modules[name] = ModuleType(name)
            setattr(modules[name], attr, object)
        spec = importlib.util.spec_from_file_location('isolated_ingestion', ROOT / 'services/ingestion-worker/src/main.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(module)
        self.worker = module.LogIngestor.__new__(module.LogIngestor)
        self.worker.ledger = IngestionLedger()
        self.worker.db = DuckDBConnector()
        self.worker.kb = Mock()
        self.worker.batch_buffer = []
        self.worker.log_event_buffer = []
        self.worker.batch_size = 2
        self.worker.parse_log = Mock(return_value=LogEvent(timestamp=datetime(2026, 9, 15),
            severity='ERROR', service_name='fixture', body='synthetic event'))
        self.source = Path('data/source/landing_zone/fixture.log')
        self.source.parent.mkdir(parents=True)
        self.source.write_text('fixture line\n')
        self.destination = Path('data/source/processed/fixture.log')
        self.destination.parent.mkdir(parents=True)
        self.fingerprint = hashlib.sha256(b'.log\0' + self.source.read_bytes()).hexdigest()

    def test_success_acknowledges_only_after_persistence(self):
        self.worker.process_file(str(self.source), str(self.destination))
        self.assertTrue(self.destination.exists())
        self.assertEqual(self.worker.ledger.status(self.fingerprint)[0], 'indexed')
        self.assertEqual(self.worker.db.query('SELECT count(*) FROM logs'), [(1,)])

    def test_database_failure_is_quarantined_not_processed(self):
        with patch.object(self.worker.db, 'persist_ingestion_batch', side_effect=RuntimeError('fixture failure')):
            with self.assertRaises(RuntimeError):
                self.worker.process_file(str(self.source), str(self.destination))
        self.assertFalse(self.destination.exists())
        self.assertTrue(list(Path('data/source/quarantine').glob('*.log')))
        self.assertEqual(self.worker.ledger.status(self.fingerprint), ('failed', 'processing_failed'))

    def test_vector_failure_preserves_visible_partial_failure(self):
        self.worker.parse_log.return_value.context = {'template_id': '1', 'template_str': 'fixture', 'change_type': 'cluster_created'}
        self.worker.kb.upsert_logs.side_effect = RuntimeError('vector unavailable')
        with self.assertRaises(RuntimeError):
            self.worker.process_file(str(self.source), str(self.destination))
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.worker.db.query('SELECT count(*) FROM logs'), [(1,)])
        self.assertEqual(self.worker.ledger.status(self.fingerprint)[0], 'failed')
        with self.assertRaisesRegex(RuntimeError, 'recovery review'):
            self.worker.ledger.claim(self.fingerprint, 'retry.log')

    def test_repeated_completed_file_does_not_duplicate_logs(self):
        raw = self.source.read_bytes()
        self.worker.process_file(str(self.source), str(self.destination))
        self.source.write_bytes(raw)
        self.worker.process_file(str(self.source), str(self.destination.with_name('retry.log')))
        self.assertEqual(self.worker.db.query('SELECT count(*) FROM logs'), [(1,)])

    def test_move_failure_can_retry_without_reingesting(self):
        self.destination.write_text('existing evidence')
        with self.assertRaises(FileExistsError):
            self.worker.process_file(str(self.source), str(self.destination))
        self.assertTrue(self.source.exists())
        self.worker.process_file(str(self.source), str(self.destination.with_name('retry.log')))
        self.assertEqual(self.worker.db.query('SELECT count(*) FROM logs'), [(1,)])

    def test_interrupted_claim_survives_restart_and_blocks_unsafe_replay(self):
        self.worker.ledger.claim(self.fingerprint, self.source.name)
        restarted = IngestionLedger()
        with self.assertRaisesRegex(RuntimeError, 'recovery review'):
            restarted.claim(self.fingerprint, self.source.name)

    def test_empty_runbook_discovery_is_not_acknowledged_as_indexed(self):
        self.source = self.source.with_suffix('.md')
        self.source.write_text('# Fixture runbook')
        self.worker.llm_client = Mock()
        self.worker.llm_client.generate.return_value = '[]'
        with self.assertRaises(ValueError):
            self.worker.process_file(str(self.source), str(self.destination.with_suffix('.md')))
        self.assertFalse(self.destination.with_suffix('.md').exists())
        self.worker.kb.add_documents.assert_not_called()

    def test_changed_input_fails_instead_of_acknowledging_different_bytes(self):
        event = self.worker.parse_log.return_value
        def parse(line):
            self.source.write_text('changed input')
            return event
        self.worker.parse_log.side_effect = parse
        with self.assertRaisesRegex(RuntimeError, 'changed'):
            self.worker.process_file(str(self.source), str(self.destination))
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.worker.ledger.status(self.fingerprint)[0], 'failed')

    def test_vector_outage_replay_does_not_duplicate_committed_events(self):
        raw = self.source.read_bytes()
        self.worker.parse_log.return_value.context = {'template_id': '1', 'template_str': 'fixture', 'change_type': 'none'}
        self.worker.kb.upsert_logs.side_effect = RuntimeError('vector unavailable')
        with self.assertRaises(RuntimeError):
            self.worker.process_file(str(self.source), str(self.destination))
        self.assertEqual(len(self.worker.db.pending_ingestion_patterns(self.fingerprint)), 1)
        self.source.write_bytes(raw)
        self.worker.kb.upsert_logs.side_effect = None
        self.worker.process_file(str(self.source), str(self.destination), replay=True)
        self.assertEqual(self.worker.db.query('SELECT count(*) FROM logs'), [(1,)])
        self.assertEqual(self.worker.db.pending_ingestion_patterns(self.fingerprint), [])
        self.assertEqual(self.worker.ledger.status(self.fingerprint)[0], 'indexed')

    def test_crash_after_vector_write_replays_same_vector_identity(self):
        raw = self.source.read_bytes()
        self.worker.parse_log.return_value.context = {'template_id': '1', 'template_str': 'fixture'}
        vectors = {}
        def upsert(events):
            for event in events:
                vectors[(event.service_name, event.context['cluster_id'])] = event.body
        self.worker.kb.upsert_logs.side_effect = upsert
        with patch.object(self.worker.db, 'complete_ingestion_pattern', side_effect=RuntimeError('crash boundary')):
            with self.assertRaises(RuntimeError):
                self.worker.process_file(str(self.source), str(self.destination))
        self.source.write_bytes(raw)
        self.worker.process_file(str(self.source), str(self.destination), replay=True)
        self.assertEqual(len(vectors), 1)
        self.assertEqual(self.worker.db.query('SELECT count(*) FROM logs'), [(1,)])

    def test_batch_failure_rolls_back_rows_and_event_keys_together(self):
        record = self.worker.parse_log.return_value.model_dump()
        first = {**record, '_event_id': 'fixture:1', '_file_id': 'fixture'}
        invalid = {**record, '_event_id': 'fixture:2', '_file_id': 'fixture', 'timestamp': 'invalid timestamp'}
        with self.assertRaises(Exception):
            self.worker.db.persist_ingestion_batch([first, invalid])
        self.assertEqual(self.worker.db.query('SELECT count(*) FROM logs'), [(0,)])
        self.worker.db.persist_ingestion_batch([first])
        self.worker.db.persist_ingestion_batch([first])
        self.assertEqual(self.worker.db.query('SELECT count(*) FROM logs'), [(1,)])

    def test_legacy_partial_ingestion_cannot_be_replayed_by_new_protocol(self):
        self.worker.ledger.claim(self.fingerprint, self.source.name, protocol=1)
        with self.assertRaisesRegex(RuntimeError, 'recovery review'):
            self.worker.process_file(str(self.source), str(self.destination), replay=True)

    def test_replay_refuses_unrecognized_source_bytes(self):
        with self.assertRaisesRegex(RuntimeError, 'exact file bytes'):
            self.worker.process_file(str(self.source), str(self.destination), replay=True)
        self.assertEqual(self.worker.db.query('SELECT count(*) FROM logs'), [(0,)])

    def test_identical_lines_remain_distinct_events(self):
        self.source.write_text('same line\n\nsame line\n')
        self.worker.process_file(str(self.source), str(self.destination))
        self.assertEqual(self.worker.db.query('SELECT count(*) FROM logs'), [(2,)])
        ids = self.worker.db.query('SELECT event_id FROM ingestion_events_v1 ORDER BY event_id')
        self.assertTrue(ids[0][0].endswith(':000000000001'))
        self.assertTrue(ids[1][0].endswith(':000000000003'))
