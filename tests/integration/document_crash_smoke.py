"""Abrupt faults in the real Markdown worker with real SQLite/Chroma, synthetic LLM."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace

from shared.document_identity import document_manifest
from shared.document_journal import DocumentJournal

RAW = b'# Recovery\r\nRestart the fixture service.\r\n'
ROOT = Path('/workspace')


def run_worker(directory, cut, replay, destination):
    # Replace only unrelated startup services; exercise the real document worker path.
    for name, attr in [('services.knowledge_base.src.store', 'KnowledgeStore'),
                       ('shared.llm.client', 'LLMClient'),
                       ('shared.db.duckdb_client', 'DuckDBConnector'),
                       ('shared.utils.template_miner', 'LogTemplateMiner'),
                       ('shared.utils.log_parser', 'LogParser'), ('janitor', 'Janitor'),
                       ('watchdog.observers', 'Observer'), ('watchdog.events', 'FileSystemEventHandler')]:
        module = ModuleType(name)
        setattr(module, attr, object)
        sys.modules[name] = module
    spec = importlib.util.spec_from_file_location('crash_worker', ROOT / 'services/ingestion-worker/src/main.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import chromadb
    from chromadb.config import Settings
    from shared.vector_upsert import upsert_document_card
    os.chdir(directory)
    collection = chromadb.PersistentClient(path='vectors', settings=Settings(anonymized_telemetry=False)).get_or_create_collection('fixture-cards')
    count_path = Path('provider_calls.json')

    def generate(prompt, **kwargs):
        calls = json.loads(count_path.read_text()) if count_path.exists() else 0
        count_path.write_text(json.dumps(calls + 1))
        return '["Recovery", "Verification"]' if 'Return only a JSON list' in prompt else 'Use the documented fixture recovery procedure.'

    def boundary(name, operation):
        def wrapped(*args, **kwargs):
            if cut == 'before_' + name:
                os._exit(73)
            result = operation(*args, **kwargs)
            if cut == 'after_' + name:
                os._exit(73)
            return result
        return wrapped

    for name in ('claim', 'save_topics', 'save_card', 'complete_card', 'finish', 'locate'):
        setattr(DocumentJournal, name, boundary(name, getattr(DocumentJournal, name)))
    module.shutil.move = boundary('move', module.shutil.move)
    embedder = SimpleNamespace(get_text_embedding=lambda text: [0.1, 0.2, 0.3])
    worker = module.LogIngestor.__new__(module.LogIngestor)
    worker.ledger = SimpleNamespace(path='journal.sqlite3')
    worker.batch_buffer = []
    worker.log_event_buffer = []
    worker.llm_client = SimpleNamespace(generate=generate)
    worker.kb = SimpleNamespace(upsert_document_card=boundary('upsert', lambda payload: upsert_document_card(collection, embedder, payload)))
    worker.process_file('landing/fixture.md', destination, replay=replay)


def parent():
    import chromadb
    from chromadb.config import Settings
    for boundary in ('claim', 'save_topics', 'save_card', 'upsert', 'complete_card', 'finish', 'move', 'locate'):
        for side in ('before', 'after'):
            cut = side + '_' + boundary
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / 'landing/fixture.md'
                source.parent.mkdir()
                source.write_bytes(RAW)
                command = [sys.executable, '-B', __file__, directory]
                result = subprocess.run(command + [cut, 'false', 'processed.md'], timeout=90)
                assert result.returncode == 73, (cut, result.returncode)
                journal = DocumentJournal(root / 'journal.sqlite3')
                manifest = document_manifest('local-files', 'fixture.md', RAW)
                with journal.connection() as conn:
                    row = conn.execute('SELECT state FROM document_versions_v1').fetchone()
                # Before the claim commits there is no durable receipt: ordinary retry is required.
                replay = row is not None
                source.write_bytes(RAW)
                subprocess.run(command + ['none', str(replay).lower(), 'recovered.md'], check=True, timeout=90)
                calls = (root / 'provider_calls.json').read_text()
                assert int(calls) == (4 if cut in ('before_save_topics', 'before_save_card') else 3), cut
                source.write_bytes(RAW)
                subprocess.run(command + ['none', 'true', 'repeated.md'], check=True, timeout=90)
                assert (root / 'provider_calls.json').read_text() == calls, cut
                assert (root / 'recovered.md').read_bytes() == RAW
                with journal.connection() as conn:
                    assert conn.execute('SELECT state,original FROM document_versions_v1').fetchall() == [('indexed', RAW)], cut
                    assert conn.execute('SELECT count(*),sum(done) FROM document_cards_v1').fetchone() == (2, 2), cut
                client = chromadb.PersistentClient(path=str(root / 'vectors'), settings=Settings(anonymized_telemetry=False))
                collection = client.get_collection('fixture-cards')
                assert collection.count() == 2, cut
                rows = collection.get()
                assert all(m['version_id'] == manifest['version_id'] for m in rows['metadatas']), cut
                assert all(m['source_sha256'] == hashlib.sha256(RAW).hexdigest() for m in rows['metadatas']), cut
                print('PASS:', cut, 'recovered two cards; repeated replay made no provider calls', flush=True)
    print('PASS: all 16 abrupt Markdown worker boundaries recovered')


if __name__ == '__main__':
    if len(sys.argv) == 5:
        run_worker(sys.argv[1], sys.argv[2], sys.argv[3] == 'true', sys.argv[4])
    else:
        parent()
