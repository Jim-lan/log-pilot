"""Dry-run reconciliation of an OFFLINE COPIED data snapshot. No apply/delete mode."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared.ingestion_reconciliation import reconcile_records

MAX_BYTES = 512 * 1024 * 1024
MAX_RECORDS = 100000


def fingerprint_tree(root):
    entries = []
    total = 0
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('Snapshots may not contain symlinks')
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError('Snapshots must contain regular files only')
        total += path.stat().st_size
        if total > MAX_BYTES or len(entries) >= MAX_RECORDS:
            raise ValueError('Snapshot exceeds the 512 MiB / 100000 file inspection bound')
        hash_value = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                hash_value.update(block)
        entries.append((str(path.relative_to(root)), path.stat().st_size, hash_value.hexdigest()))
    entries.sort()
    return entries


def ledger_records(root):
    path = root / 'state/ingestion.sqlite3'
    if not path.is_file():
        raise ValueError('Snapshot is missing its ingestion ledger')
    conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        claims, cards = [], []
        if 'files' in tables:
            columns = {r[1] for r in conn.execute('PRAGMA table_info(files)')}
            protocol = 'protocol' if 'protocol' in columns else '1'
            claims = [dict(zip(('fingerprint', 'state', 'protocol'), row)) for row in conn.execute(
                'SELECT fingerprint,state,' + protocol + ' FROM files LIMIT ?', (MAX_RECORDS + 1,))]
        if 'document_cards_v1' in tables:
            for payload, done in conn.execute('SELECT payload,done FROM document_cards_v1 LIMIT ?', (MAX_RECORDS + 1,)):
                card = json.loads(payload)
                cards.append({'node_id': card['node_id'], 'text': card['text'], 'done': done})
        return claims, cards
    finally:
        conn.close()


def inspect_snapshot(snapshot):
    snapshot = Path(snapshot).resolve()
    live = (ROOT / 'data').resolve()
    if not snapshot.is_dir() or snapshot == live or live in snapshot.parents or snapshot in live.parents:
        raise ValueError('Supply a separate offline copied data snapshot, not application data or its parent')
    before = fingerprint_tree(snapshot)
    with tempfile.TemporaryDirectory(prefix='logpilot-reconcile-') as directory:
        working = Path(directory) / 'data'
        shutil.copytree(snapshot, working)
        if fingerprint_tree(working) != before or fingerprint_tree(snapshot) != before:
            raise ValueError('Snapshot changed while copying; stop writers and create a consistent copy')
        claims, cards = ledger_records(working)
        vector_path = working / 'target/vector_store'
        if not vector_path.is_dir():
            raise ValueError('Snapshot is missing its vector store')
        # Chroma may initialize/migrate internal state; open ONLY the disposable second copy.
        import chromadb
        from chromadb.config import Settings
        client = chromadb.PersistentClient(path=str(vector_path), settings=Settings(anonymized_telemetry=False))
        collection = client.get_collection('log_pilot_kb')
        count = collection.count()
        if count > MAX_RECORDS:
            raise ValueError('Vector inventory exceeds the record bound')
        vectors = []
        for offset in range(0, count, 500):
            batch = collection.get(limit=500, offset=offset, include=['documents', 'metadatas'])
            vectors.extend({'id': node_id, 'document': text, 'metadata': metadata}
                           for node_id, text, metadata in zip(batch['ids'], batch['documents'], batch['metadatas']))
        if len(vectors) != count:
            raise ValueError('Incomplete vector inventory')
        report = reconcile_records(vectors, claims, cards, MAX_RECORDS)
    if fingerprint_tree(snapshot) != before:
        raise ValueError('Source snapshot changed during inspection')
    report['snapshot'] = {'sha256': hashlib.sha256(json.dumps(before, separators=(',', ':')).encode()).hexdigest(),
                          'files': len(before), 'bytes': sum(row[1] for row in before),
                          'source_unchanged': True}
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot-dir', required=True)
    parser.add_argument('--report-file', required=True)
    args = parser.parse_args()
    output = Path(args.report_file).resolve()
    source = Path(args.snapshot_dir).resolve()
    live = (ROOT / 'data').resolve()
    if source == output or source in output.parents or live == output or live in output.parents:
        parser.error('Report must be outside source snapshot and application data')
    try:
        report = inspect_snapshot(source)
        with output.open('x') as stream:
            json.dump(report, stream, indent=2)
        print('Dry-run report created. Source unchanged; no records modified. Review required.')
    except Exception:
        raise SystemExit('Reconciliation failed; no apply/delete operation was attempted. Verify snapshot, schema, limits and unused report path.') from None
