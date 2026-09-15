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
        with patch.object(self.worker.db, 'insert_batch', side_effect=RuntimeError('fixture failure')):
            with self.assertRaises(RuntimeError):
                self.worker.process_file(str(self.source), str(self.destination))
        self.assertFalse(self.destination.exists())
        self.assertTrue(list(Path('data/source/quarantine').glob('*.log')))
        self.assertEqual(self.worker.ledger.status(self.fingerprint), ('failed', 'processing_failed'))

    def test_vector_failure_preserves_visible_partial_failure(self):
        self.worker.parse_log.return_value.context = {'template_id': '1', 'template_str': 'fixture', 'change_type': 'cluster_created'}
        self.worker.kb.add_logs.side_effect = RuntimeError('vector unavailable')
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
