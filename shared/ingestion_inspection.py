"""Read-only, bounded recovery metadata inspection; never include source/payload text."""
from pathlib import Path
import sqlite3
import duckdb


def inspect_ingestion(data_dir='data', limit=100):
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('Inspection limit must be from 1 to 1000')
    root = Path(data_dir)
    result = {'log_claims': [], 'documents': [], 'pending_patterns': [], 'unavailable': [], 'limit': limit, 'truncated': []}
    ledger = root / 'state/ingestion.sqlite3'
    if ledger.exists():
        conn = None
        try:
            conn = sqlite3.connect(ledger.resolve().as_uri() + '?mode=ro', uri=True)
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'files' in tables:
                columns = {row[1] for row in conn.execute('PRAGMA table_info(files)')}
                protocol = 'protocol' if 'protocol' in columns else '1'
                result['log_claims'] = [dict(zip(('fingerprint', 'state', 'failure_code', 'protocol'), row)) for row in conn.execute(
                    'SELECT fingerprint,state,failure_code,' + protocol + " FROM files ORDER BY CASE WHEN state='indexed' THEN 1 ELSE 0 END,rowid LIMIT ?", (limit + 1,))]
            if 'document_versions_v1' in tables:
                result['documents'] = [dict(zip(('version_id', 'state', 'failure_code'), row)) for row in conn.execute(
                    "SELECT version_id,state,failure_code FROM document_versions_v1 ORDER BY CASE WHEN state='indexed' THEN 1 ELSE 0 END,rowid LIMIT ?", (limit + 1,))]
        except sqlite3.Error:
            result['unavailable'].append('ledger')
        finally:
            if conn is not None:
                conn.close()
    else:
        result['unavailable'].append('ledger_missing')
    logs = root / 'target/logs.duckdb'
    if logs.exists():
        try:
            with duckdb.connect(str(logs), read_only=True, config={'enable_external_access': False}) as conn:
                exists = conn.execute("SELECT 1 FROM information_schema.tables WHERE table_name='ingestion_outbox_v1'").fetchone()
                if exists:
                    result['pending_patterns'] = [dict(zip(('file_id', 'pending_count'), row)) for row in conn.execute(
                        'SELECT file_id,count(*) FROM ingestion_outbox_v1 WHERE NOT done GROUP BY file_id ORDER BY file_id LIMIT ?', [limit + 1]).fetchall()]
        except duckdb.Error:
            result['unavailable'].append('analytics')
    else:
        result['unavailable'].append('analytics_missing')
    for section in ('log_claims', 'documents', 'pending_patterns'):
        if len(result[section]) > limit:
            result['truncated'].append(section)
            result[section] = result[section][:limit]
    return result
