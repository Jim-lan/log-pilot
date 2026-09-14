"""Version 1 evaluation storage. Reads never initialize or migrate a database."""
import json
from datetime import datetime, timedelta
from pathlib import Path

import duckdb


class EvaluationStore:
    def __init__(self, path):
        self.path = path

    def start(self, run_id, case_ids, provenance, timestamp=None):
        if len(set(case_ids)) != len(case_ids) or not case_ids:
            raise ValueError('Evaluation requires unique, nonempty case IDs')
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with duckdb.connect(self.path) as conn:
            conn.execute('BEGIN')
            conn.execute('''CREATE TABLE IF NOT EXISTS evaluation_runs_v1 (
                run_id VARCHAR PRIMARY KEY, timestamp TIMESTAMP, status VARCHAR,
                provenance VARCHAR, failure_code VARCHAR)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS evaluation_cases_v1 (
                run_id VARCHAR, case_id VARCHAR, status VARCHAR, latency DOUBLE,
                evidence VARCHAR, failure_code VARCHAR, PRIMARY KEY(run_id, case_id))''')
            conn.execute('INSERT INTO evaluation_runs_v1 VALUES (?, ?, ?, ?, NULL)',
                         [run_id, timestamp or datetime.utcnow(), 'running', json.dumps(provenance)])
            conn.executemany('INSERT INTO evaluation_cases_v1 VALUES (?, ?, ?, NULL, NULL, NULL)',
                             [[run_id, case_id, 'pending'] for case_id in case_ids])
            conn.execute('COMMIT')

    def record(self, run_id, case_id, status, latency, evidence, failure_code=None):
        import math
        if status not in ('passed', 'failed', 'error', 'unscored'):
            raise ValueError('Invalid case status')
        if not math.isfinite(latency) or latency < 0:
            raise ValueError('Invalid latency')
        with duckdb.connect(self.path) as conn:
            conn.execute('BEGIN')
            row = conn.execute("SELECT case_id FROM evaluation_cases_v1 WHERE run_id=? AND case_id=? AND status='pending'",
                               [run_id, case_id]).fetchone()
            if not row:
                raise ValueError('Case missing or already recorded')
            # DuckDB 1.1.3 UPDATE RETURNING hits an indexed-row constraint bug.
            conn.execute("""UPDATE evaluation_cases_v1 SET status=?, latency=?, evidence=?, failure_code=?
                WHERE run_id=? AND case_id=?""",
                [status, latency, json.dumps(evidence), failure_code, run_id, case_id])
            conn.execute('COMMIT')

    def finish(self, run_id, failure_code=None):
        with duckdb.connect(self.path) as conn:
            conn.execute('BEGIN')
            pending = conn.execute("SELECT count(*) FROM evaluation_cases_v1 WHERE run_id=? AND status='pending'", [run_id]).fetchone()[0]
            if pending:
                failure_code = failure_code or 'incomplete_run'
                conn.execute("UPDATE evaluation_cases_v1 SET status='error', failure_code=? WHERE run_id=? AND status='pending'", [failure_code, run_id])
            errors = conn.execute("SELECT count(*) FROM evaluation_cases_v1 WHERE run_id=? AND status='error'", [run_id]).fetchone()[0]
            status = 'failed' if failure_code else ('completed_with_errors' if errors else 'completed')
            conn.execute('UPDATE evaluation_runs_v1 SET status=?, failure_code=? WHERE run_id=?', [status, failure_code, run_id])
            conn.execute('COMMIT')

    def summary(self, now=None):
        empty = dict(schema_version=1, status='unavailable', pass_rate_24h=None,
                     avg_latency_24h=None, total_runs=None, history=[])
        if not Path(self.path).exists():
            return empty
        try:
            with duckdb.connect(self.path, read_only=True) as conn:
                start = (now or datetime.utcnow()) - timedelta(hours=24)
                end = now or datetime.utcnow()
                rate, latency = conn.execute('''SELECT
                    100.0 * count(*) FILTER (WHERE c.status='passed') / nullif(count(*), 0), avg(c.latency)
                    FROM evaluation_cases_v1 c JOIN evaluation_runs_v1 r USING(run_id)
                    WHERE r.timestamp >= ? AND r.timestamp <= ?''', [start, end]).fetchone()
                total = conn.execute('SELECT count(*) FROM evaluation_runs_v1').fetchone()[0]
                history = conn.execute('''SELECT r.run_id, r.timestamp, r.status,
                    100.0 * count(*) FILTER (WHERE c.status='passed') / nullif(count(c.case_id), 0)
                    FROM evaluation_runs_v1 r LEFT JOIN evaluation_cases_v1 c USING(run_id)
                    GROUP BY r.run_id, r.timestamp, r.status ORDER BY r.timestamp DESC LIMIT 10''').fetchall()
                return dict(schema_version=1, status='available', pass_rate_24h=round(rate, 1) if rate is not None else None,
                            avg_latency_24h=round(latency, 2) if latency is not None else None, total_runs=total,
                            history=[dict(run_id=r[0], timestamp=str(r[1]), status=r[2], pass_rate=r[3]) for r in history])
        except duckdb.Error:
            return empty
