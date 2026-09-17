"""File acknowledgement ledger with explicit protocol-gated log replay."""
import sqlite3
from pathlib import Path


class IngestionLedger:
    def __init__(self, path='data/state/ingestion.sqlite3'):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS files (
                fingerprint TEXT PRIMARY KEY, name TEXT NOT NULL, state TEXT NOT NULL,
                failure_code TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
            if 'protocol' not in {row[1] for row in conn.execute('PRAGMA table_info(files)')}:
                conn.execute('ALTER TABLE files ADD COLUMN protocol INTEGER NOT NULL DEFAULT 1')

    def claim(self, fingerprint, name, *, protocol=1, replay=False):
        with sqlite3.connect(self.path) as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT state,protocol FROM files WHERE fingerprint=?', (fingerprint,)).fetchone()
            if row:
                if row[0] == 'indexed':
                    return False
                if replay and protocol == 2 and row[1] == 2:
                    conn.execute("UPDATE files SET state='processing',failure_code=NULL WHERE fingerprint=?", (fingerprint,))
                    return True
                raise RuntimeError('Prior incomplete ingestion requires recovery review')
            if replay:
                raise RuntimeError('Replay requires an existing claim for these exact file bytes')
            conn.execute("INSERT INTO files(fingerprint,name,state,protocol) VALUES (?,?,'pending',?)", (fingerprint, name, protocol))
            conn.execute("UPDATE files SET state='processing' WHERE fingerprint=?", (fingerprint,))
            return True

    def mark(self, fingerprint, state, failure_code=None):
        allowed = {'persisted': {'processing'}, 'indexed': {'processing', 'persisted'},
                   'failed': {'processing', 'persisted'}}
        if state not in allowed:
            raise ValueError('Invalid ingestion state')
        with sqlite3.connect(self.path) as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT state FROM files WHERE fingerprint=?', (fingerprint,)).fetchone()
            if not row or row[0] not in allowed[state]:
                raise ValueError('Invalid ingestion transition')
            conn.execute('UPDATE files SET state=?,failure_code=?,updated_at=CURRENT_TIMESTAMP WHERE fingerprint=?',
                         (state, failure_code, fingerprint))

    def status(self, fingerprint):
        with sqlite3.connect(self.path) as conn:
            return conn.execute('SELECT state,failure_code FROM files WHERE fingerprint=?', (fingerprint,)).fetchone()
