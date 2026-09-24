"""Additive single-worker Markdown journal; persist generated work before indexing."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3

from shared.document_identity import document_manifest, document_span, card_identity


class InvalidDocumentInput(ValueError):
    """A permanent discovery/card validation failure, not a journal integrity error."""


class DocumentJournal:
    def __init__(self, path='data/state/ingestion.sqlite3'):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS document_versions_v1 (
                version_id TEXT PRIMARY KEY, source_id TEXT NOT NULL UNIQUE,
                manifest TEXT NOT NULL, original BLOB NOT NULL, topics TEXT,
                state TEXT NOT NULL, failure_code TEXT, location TEXT NOT NULL)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS document_cards_v1 (
                version_id TEXT NOT NULL, ordinal INTEGER NOT NULL, payload TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(version_id, ordinal))''')

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def claim(self, manifest, raw, location, *, replay=False):
        # Reject caller-supplied metadata that does not describe these exact bytes.
        if manifest != document_manifest(manifest['namespace'], manifest['source_key'], raw):
            raise ValueError('Document manifest does not match source bytes')
        version = manifest['version_id']
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            legacy_exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='files'").fetchone()
            if legacy_exists:
                fingerprint = hashlib.sha256(b'.md\0' + raw).hexdigest()
                if conn.execute('SELECT 1 FROM files WHERE fingerprint=?', (fingerprint,)).fetchone():
                    raise RuntimeError('Legacy Markdown requires recovery review')
            row = conn.execute('SELECT state,original FROM document_versions_v1 WHERE version_id=?', (version,)).fetchone()
            if row:
                if row[1] != raw:
                    raise ValueError('Journal source integrity failure')
                if row[0] == 'indexed':
                    return False
                if not replay:
                    raise RuntimeError('Incomplete document requires explicit replay')
                conn.execute("UPDATE document_versions_v1 SET state='processing',failure_code=NULL WHERE version_id=?", (version,))
                return True
            if replay:
                raise RuntimeError('Replay requires a known document version and exact bytes')
            if conn.execute('SELECT 1 FROM document_versions_v1 WHERE source_id=?', (manifest['source_id'],)).fetchone():
                raise RuntimeError('Document version replacement requires explicit migration review')
            conn.execute("INSERT INTO document_versions_v1 VALUES (?,?,?,?,NULL,'processing',NULL,?)",
                         (version, manifest['source_id'], json.dumps(manifest), raw, str(location)))
            return True

    def manifest_for_replay(self, version, raw):
        with self.connection() as conn:
            row = conn.execute('SELECT manifest,original FROM document_versions_v1 WHERE version_id=?', (version,)).fetchone()
        if not row or row[1] != raw:
            raise RuntimeError('Replay requires a known document version and exact bytes')
        return json.loads(row[0])

    def topics(self, version):
        with self.connection() as conn:
            row = conn.execute('SELECT topics FROM document_versions_v1 WHERE version_id=?', (version,)).fetchone()
        return json.loads(row[0]) if row and row[0] is not None else None

    def save_topics(self, version, topics):
        if (not isinstance(topics, list) or not 1 <= len(topics) <= 32 or
                any(not isinstance(t, str) or not t.strip() or len(t) > 200 for t in topics) or
                len(set(topics)) != len(topics)):
            raise InvalidDocumentInput('Invalid or excessive discovered topics')
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT topics,state FROM document_versions_v1 WHERE version_id=?', (version,)).fetchone()
            if not row or row[1] != 'processing':
                raise RuntimeError('Document is not processing')
            if row[0] is not None:
                if json.loads(row[0]) != topics:
                    raise ValueError('Cannot replace a committed document plan')
                return
            conn.execute('UPDATE document_versions_v1 SET topics=? WHERE version_id=?', (json.dumps(topics), version))

    def card(self, version, ordinal):
        with self.connection() as conn:
            row = conn.execute('SELECT payload,done FROM document_cards_v1 WHERE version_id=? AND ordinal=?', (version, ordinal)).fetchone()
        return (json.loads(row[0]), bool(row[1])) if row else None

    def save_card(self, version, ordinal, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 65536:
            raise InvalidDocumentInput('Invalid or excessive synthesized card')
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT manifest,original,topics,state FROM document_versions_v1 WHERE version_id=?', (version,)).fetchone()
            if not row or row[3] != 'processing' or row[2] is None:
                raise RuntimeError('Document has no processing plan')
            manifest, raw, topics = json.loads(row[0]), row[1], json.loads(row[2])
            node_id = card_identity(version, ordinal)
            if ordinal >= len(topics):
                raise ValueError('Card is outside the committed plan')
            payload = {'node_id': node_id, 'text': text, 'metadata': {
                'type': 'runbook_card', 'source': manifest['source_key'], 'topic': topics[ordinal],
                'namespace': manifest['namespace'], 'source_id': manifest['source_id'],
                'version_id': version, 'source_sha256': manifest['content_sha256'],
                'card_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                'derivation_version': 'document-card-v1',
                'source_spans': json.dumps([document_span(raw, 0, len(raw))]),
                'span_scope': 'whole_document_input'}}
            previous = conn.execute('SELECT payload FROM document_cards_v1 WHERE version_id=? AND ordinal=?', (version, ordinal)).fetchone()
            if previous:
                if json.loads(previous[0]) != payload:
                    raise ValueError('Cannot replace a committed card')
                return
            conn.execute('INSERT INTO document_cards_v1(version_id,ordinal,payload) VALUES (?,?,?)', (version, ordinal, json.dumps(payload)))

    def complete_card(self, version, ordinal):
        with self.connection() as conn:
            cursor = conn.execute('UPDATE document_cards_v1 SET done=1 WHERE version_id=? AND ordinal=?', (version, ordinal))
            if cursor.rowcount != 1:
                raise RuntimeError('Cannot acknowledge an unknown card')

    def finish(self, version):
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT topics,state FROM document_versions_v1 WHERE version_id=?', (version,)).fetchone()
            done = conn.execute('SELECT count(*) FROM document_cards_v1 WHERE version_id=? AND done=1', (version,)).fetchone()[0]
            if not row or row[1] != 'processing' or row[0] is None or done != len(json.loads(row[0])):
                raise RuntimeError('Cannot acknowledge incomplete document')
            conn.execute("UPDATE document_versions_v1 SET state='indexed',failure_code=NULL WHERE version_id=?", (version,))

    def failed(self, version):
        with self.connection() as conn:
            conn.execute("UPDATE document_versions_v1 SET state='failed',failure_code='processing_failed' WHERE version_id=? AND state='processing'", (version,))

    def locate(self, version, location):
        with self.connection() as conn:
            conn.execute('UPDATE document_versions_v1 SET location=? WHERE version_id=?', (str(location), version))
