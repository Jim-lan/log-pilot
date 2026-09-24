"""Real Chroma snapshot inspection preserves the supplied offline snapshot exactly."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def create_fixture(root):
    import chromadb
    from chromadb.config import Settings
    from shared.ingestion_ledger import IngestionLedger
    ledger = IngestionLedger(root / 'state/ingestion.sqlite3')
    ledger.claim('legacy-fixture', 'private-source.log', protocol=1)
    client = chromadb.PersistentClient(path=str(root / 'target/vector_store'), settings=Settings(anonymized_telemetry=False))
    collection = client.get_or_create_collection('log_pilot_kb')
    collection.add(ids=['legacy-a', 'legacy-b'], documents=['private fixture text', 'private fixture text'],
                   embeddings=[[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]],
                   metadatas=[{'service_name': 'fixture', 'cluster_id': '1'}] * 2)


def parent():
    spec = importlib.util.spec_from_file_location('reconciliation_cli', '/workspace/scripts/reconcile_ingestion_snapshot.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as directory:
        snapshot = Path(directory) / 'snapshot'
        snapshot.mkdir()
        subprocess.run([sys.executable, '-B', __file__, str(snapshot)], check=True, timeout=60)
        before = module.fingerprint_tree(snapshot)
        report = module.inspect_snapshot(snapshot)
        assert module.fingerprint_tree(snapshot) == before
        assert report['snapshot']['source_unchanged'] is True
        assert report['counts'] == {'vectors': 2, 'claims': 1, 'journal_cards': 0}
        assert report['pattern_groups'][0]['status'] == 'duplicate_text_candidate'
        assert report['mutations'] == 0
        assert 'private fixture text' not in json.dumps(report)
        assert 'private-source.log' not in json.dumps(report)
        output = Path(directory) / 'report.json'
        command = [sys.executable, '-B', '/workspace/scripts/reconcile_ingestion_snapshot.py',
                   '--snapshot-dir', str(snapshot), '--report-file', str(output)]
        subprocess.run(command, check=True, timeout=60)
        saved = output.read_bytes()
        assert json.loads(saved) == report
        assert subprocess.run(command, timeout=60, capture_output=True).returncode != 0
        assert output.read_bytes() == saved
        assert module.fingerprint_tree(snapshot) == before
        (snapshot / 'unsafe-link').symlink_to(snapshot / 'state/ingestion.sqlite3')
        try:
            module.inspect_snapshot(snapshot)
        except ValueError:
            pass
        else:
            raise AssertionError('Symlink snapshot was accepted')
        print('PASS: real-vector dry run reports legacy duplicates without altering source snapshot or exposing source text')


if __name__ == '__main__':
    if len(sys.argv) == 2:
        create_fixture(Path(sys.argv[1]))
    else:
        parent()
