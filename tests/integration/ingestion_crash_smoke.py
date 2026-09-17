"""Process-crash boundaries inside the disposable no-network Docker profile."""
import os
from pathlib import Path
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from datetime import datetime
import duckdb
from shared.db.duckdb_client import DuckDBConnector

for boundary in ('before_commit', 'after_commit'):
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        db = DuckDBConnector()
        record = {'timestamp': datetime(2026, 9, 17), 'severity': 'ERROR', 'service_name': 'fixture',
                  'body': 'synthetic', 'context': {}, '_event_id': 'fixture:1', '_file_id': 'fixture',
                  '_pattern': {'body': 'synthetic pattern'}}
        pid = os.fork()
        if pid == 0:
            class CrashConnection:
                def __enter__(self):
                    self.conn = duckdb.connect(db.db_path)
                    return self
                def __exit__(self, *args):
                    self.conn.close()
                def execute(self, sql, *args):
                    if sql == 'COMMIT' and boundary == 'before_commit':
                        os._exit(17)
                    result = self.conn.execute(sql, *args)
                    if sql == 'COMMIT' and boundary == 'after_commit':
                        os._exit(18)
                    return result
            db._get_connection = CrashConnection
            db.persist_ingestion_batch([record])
            os._exit(99)
        _, status = os.waitpid(pid, 0)
        assert os.waitstatus_to_exitcode(status) == (17 if boundary == 'before_commit' else 18)
        expected = 0 if boundary == 'before_commit' else 1
        assert db.query('SELECT count(*) FROM logs') == [(expected,)]
        db.persist_ingestion_batch([record])
        db.persist_ingestion_batch([record])
        assert db.query('SELECT count(*) FROM logs') == [(1,)]
        assert db.ingestion_event_committed('fixture:1')
        assert len(db.pending_ingestion_patterns('fixture')) == 1
        print('PASS:', boundary, 'recovery retains one event and one indexing task')
        os.chdir('/tmp')
