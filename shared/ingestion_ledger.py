"""Local file acknowledgement ledger, separate from future transactional replay."""
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

    def claim(self, fingerprint, name):
        with sqlite3.connect(self.path) as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT state FROM files WHERE fingerprint=?', (fingerprint,)).fetchone()
            if row:
                if row[0] == 'indexed':
                    return False
                raise RuntimeError('Prior incomplete ingestion requires recovery review')
            conn.execute("INSERT INTO files(fingerprint,name,state) VALUES (?,?,'pending')", (fingerprint, name))
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
