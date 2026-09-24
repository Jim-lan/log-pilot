import os
import tempfile
import unittest
from pathlib import Path

import duckdb
from shared.sql_policy import validate_query, execute_query, SQLPolicyError


class SQLPolicyContracts(unittest.TestCase):
    def test_supported_analytics(self):
        for sql in ["SELECT count(*) FROM logs", "SELECT severity,count(*) FROM logs GROUP BY severity",
                    "SELECT * FROM logs WHERE timestamp > now()-INTERVAL '1 HOURS' LIMIT 5",
                    "SELECT context->>'$.key' FROM logs", "SELECT l.service_name, c.department FROM logs l JOIN system_catalog c ON l.app_id=c.system_name",
                    "WITH counts AS (SELECT severity, count(*) n FROM logs GROUP BY severity) SELECT * FROM counts"]:
            with self.subTest(sql=sql):
                self.assertTrue(validate_query(sql))

    def test_boolean_conditions_preserve_policy_on_nested_expressions(self):
        self.assertTrue(validate_query("SELECT body FROM logs WHERE service_name='cache' AND (severity='ERROR' OR NOT body='ignored')"))
        for condition in ["severity='ERROR' AND getenv('HOME')='x'",
                          "severity='ERROR' OR EXISTS(SELECT * FROM secret)",
                          "NOT EXISTS(SELECT * FROM read_csv('/tmp/private'))"]:
            with self.subTest(condition=condition), self.assertRaises(SQLPolicyError):
                validate_query('SELECT body FROM logs WHERE ' + condition)

    def test_forbidden_operations_fail_closed(self):
        for sql in ["SELECT * FROM read_csv('/tmp/private')", "SELECT * FROM '/tmp/private.csv'",
                    "SELECT 1; COPY logs TO '/tmp/leak'", "ATTACH '/tmp/private' AS secret",
                    "INSTALL httpfs", "LOAD httpfs", "PRAGMA database_list", "SET enable_external_access=true",
                    "DELETE FROM logs", "SELECT * FROM sqlite_scan('/tmp/private','users')",
                    "SELECT * FROM information_schema.tables", "SELECT * FROM secret", "SELECT secret FROM logs",
                    "SELECT secret AS secret FROM logs", "SELECT * FROM other.logs",
                    "SELECT getenv('HOME')", "SELECT * FROM query('SELECT * FROM secret')",
                    "WITH x AS (SELECT * FROM read_parquet('https://fixture.invalid/x')) SELECT * FROM x",
                    "WITH x AS (WITH secret AS (SELECT 1) SELECT * FROM secret) SELECT count(*) FROM secret"]:
            with self.subTest(sql=sql), self.assertRaises(SQLPolicyError):
                validate_query(sql)

    def test_expensive_query_is_interrupted_and_next_query_succeeds(self):
        with tempfile.TemporaryDirectory(dir=os.environ['LOGPILOT_TEST_SCRATCH']) as tmp:
            path = str(Path(tmp) / 'logs.duckdb')
            with duckdb.connect(path) as conn:
                conn.execute('CREATE TABLE logs AS SELECT range AS body FROM range(1000)')
            with self.assertRaisesRegex(SQLPolicyError, 'deadline'):
                execute_query(path, 'SELECT sum(CAST(a.body AS DOUBLE)*CAST(b.body AS DOUBLE)*CAST(c.body AS DOUBLE)) FROM logs a, logs b, logs c', timeout=0.01)
            self.assertEqual(execute_query(path, 'SELECT count(*) FROM logs'), [(1000,)])

    def test_real_executor_caps_rows_and_releases_connection(self):
        with tempfile.TemporaryDirectory(dir=os.environ['LOGPILOT_TEST_SCRATCH']) as tmp:
            path = str(Path(tmp) / 'logs.duckdb')
            with duckdb.connect(path) as conn:
                conn.execute('CREATE TABLE logs(body VARCHAR)')
                conn.execute("INSERT INTO logs VALUES ('a'),('b'),('c')")
            self.assertEqual(execute_query(path, 'SELECT count(*) FROM logs'), [(3,)])
            with self.assertRaises(SQLPolicyError):
                execute_query(path, 'SELECT body FROM logs', max_rows=2)
            self.assertEqual(execute_query(path, "SELECT body FROM logs WHERE body='a'"), [('a',)])

    def test_engine_disables_external_access_even_if_policy_is_bypassed_in_test(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir=os.environ['LOGPILOT_TEST_SCRATCH']) as tmp:
            path = str(Path(tmp) / 'logs.duckdb')
            with duckdb.connect(path):
                pass
            secret = Path(tmp) / 'fixture.csv'
            secret.write_text('body\nprivate fixture\n')
            with patch('shared.sql_policy.validate_query', return_value=f"SELECT * FROM read_csv('{secret}')"):
                with self.assertRaises(duckdb.Error):
                    execute_query(path, 'fixture')
