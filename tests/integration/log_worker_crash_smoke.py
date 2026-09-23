"""Real log worker crash/replay with DuckDB/SQLite and a durable vector test double."""
import hashlib
import importlib.util
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from types import ModuleType, SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.db.duckdb_client import DuckDBConnector
from shared.ingestion_ledger import IngestionLedger
from shared.log_schema import LogEvent

RAW = b'fixture log line\n'
ROOT = Path(__file__).resolve().parents[2]


def run_worker(directory, cut, replay, destination):
    for name, attr in [('services.knowledge_base.src.store', 'KnowledgeStore'),
                       ('shared.llm.client', 'LLMClient'),
                       ('shared.utils.template_miner', 'LogTemplateMiner'),
                       ('shared.utils.log_parser', 'LogParser'), ('janitor', 'Janitor'),
                       ('watchdog.observers', 'Observer'), ('watchdog.events', 'FileSystemEventHandler')]:
        module = ModuleType(name)
        setattr(module, attr, object)
        sys.modules[name] = module
    spec = importlib.util.spec_from_file_location('crash_log_worker', ROOT / 'services/ingestion-worker/src/main.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    os.chdir(directory)

    def boundary(name, operation):
        def wrapped(*args, **kwargs):
            if cut == 'before_' + name:
                os._exit(73)
            result = operation(*args, **kwargs)
            if cut == 'after_' + name:
                os._exit(73)
            return result
        return wrapped

    def upsert(events):
        # Independent durable sink tests the outbox/ack handshake, not Chroma internals.
        conn = sqlite3.connect('vector-double.sqlite3')
        try:
            with conn:
                conn.execute('CREATE TABLE IF NOT EXISTS vectors (id TEXT PRIMARY KEY, body TEXT)')
                for event in events:
                    conn.execute('INSERT OR REPLACE INTO vectors VALUES (?,?)',
                                 (event.service_name + ':' + str(event.context['cluster_id']), event.body))
        finally:
            conn.close()

    worker = module.LogIngestor.__new__(module.LogIngestor)
    worker.db = DuckDBConnector()
    worker.ledger = IngestionLedger()
    worker.batch_buffer = []
    worker.log_event_buffer = []
    worker.batch_size = 2
    worker.parse_log = lambda line: LogEvent(timestamp=datetime(2026, 9, 23), severity='ERROR',
        service_name='fixture', body='fixture', context={'template_id': '1', 'template_str': 'fixture pattern'})
    worker.kb = SimpleNamespace(upsert_logs=boundary('upsert', upsert))
    for name in ('persist_ingestion_batch', 'complete_ingestion_pattern'):
        setattr(worker.db, name, boundary(name, getattr(worker.db, name)))
    worker.ledger.claim = boundary('claim', worker.ledger.claim)
    original_mark = worker.ledger.mark
    worker.ledger.mark = lambda fingerprint, state, *args: boundary('mark_' + state, original_mark)(fingerprint, state, *args)
    module.shutil.move = boundary('move', module.shutil.move)
    worker.process_file('landing/fixture.log', destination, replay=replay)


def parent():
    for boundary in ('claim', 'persist_ingestion_batch', 'upsert', 'complete_ingestion_pattern',
                     'mark_persisted', 'mark_indexed', 'move'):
        for side in ('before', 'after'):
            cut = side + '_' + boundary
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / 'landing/fixture.log'
                source.parent.mkdir()
                source.write_bytes(RAW)
                command = [sys.executable, '-B', __file__, directory]
                result = subprocess.run(command + [cut, 'false', 'processed.log'], timeout=45)
                assert result.returncode == 73, (cut, result.returncode)
                fingerprint = hashlib.sha256(b'.log\0' + RAW).hexdigest()
                ledger = IngestionLedger(root / 'data/state/ingestion.sqlite3')
                replay = ledger.status(fingerprint) is not None
                source.write_bytes(RAW)
                subprocess.run(command + ['none', str(replay).lower(), 'recovered.log'], check=True, timeout=45)
                source.write_bytes(RAW)
                subprocess.run(command + ['none', 'true', 'repeated.log'], check=True, timeout=45)
                conn = sqlite3.connect(root / 'vector-double.sqlite3')
                try:
                    assert conn.execute('SELECT count(*) FROM vectors').fetchone() == (1,), cut
                finally:
                    conn.close()
                import duckdb
                with duckdb.connect(str(root / 'data/target/logs.duckdb'), read_only=True) as db:
                    assert db.execute('SELECT count(*) FROM logs').fetchone() == (1,), cut
                    assert db.execute('SELECT count(*) FROM ingestion_events_v1').fetchone() == (1,), cut
                    assert db.execute('SELECT count(*) FROM ingestion_outbox_v1 WHERE NOT done').fetchone() == (0,), cut
                assert ledger.status(fingerprint) == ('indexed', None), cut
                assert (root / 'recovered.log').read_bytes() == RAW
                print('PASS:', cut, 'one row, event and vector; no pending index jobs', flush=True)
    print('PASS: all 14 abrupt log worker boundaries recovered')


if __name__ == '__main__':
    if len(sys.argv) == 5:
        run_worker(sys.argv[1], sys.argv[2], sys.argv[3] == 'true', sys.argv[4])
    else:
        parent()
