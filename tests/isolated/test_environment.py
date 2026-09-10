"""Safety checks and small real-storage baseline, not full agent/E2E coverage."""
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class IsolatedEnvironment(unittest.TestCase):
    def setUp(self):
        if "LOGPILOT_TEST_SCRATCH" not in os.environ:
            raise RuntimeError("Use scripts/run_isolated_tests.py; do not collect this suite directly")
        self.previous = Path.cwd()
        self.directory = tempfile.TemporaryDirectory(dir=os.environ["LOGPILOT_TEST_SCRATCH"])
        os.chdir(self.directory.name)
        self.addCleanup(self.restore)

    def restore(self):
        os.chdir(self.previous)
        self.directory.cleanup()

    def connector(self):
        from shared.db.duckdb_client import DuckDBConnector
        return DuckDBConnector()

    def test_fresh_scratch_and_relative_storage(self):
        self.assertFalse(Path("data").exists())
        db = self.connector()
        self.assertEqual(db.query("SELECT count(*) FROM logs"), [(0,)])
        self.assertTrue(Path("data/target/logs.duckdb").exists())
        self.assertTrue(Path("data/target/history.duckdb").exists())
        self.assertIn(Path(os.environ["LOGPILOT_TEST_SCRATCH"]), Path.cwd().parents)

    def test_synthetic_parse_mask_store_query(self):
        from shared.utils.log_parser import LogParser
        from shared.utils.pii_masker import PIIMasker
        records = [PIIMasker().mask_context(LogParser().parse(line)) for line in
                   (ROOT / "tests/isolated/fixtures/sample.log").read_text().splitlines()]
        db = self.connector()
        db.insert_batch(records)
        self.assertEqual(db.query("SELECT severity, count(*) FROM logs GROUP BY severity ORDER BY severity"), [("ERROR", 2), ("INFO", 1)])
        bodies = str(db.query("SELECT body, context FROM logs"))
        self.assertNotIn("learner@example.com", bodies)
        self.assertIn("<EMAIL_REDACTED>", bodies)
        self.assertEqual(db.query("SELECT * FROM logs WHERE service_name = ?", ["absent"]), [])

    def test_history_roundtrip_in_disposable_database(self):
        db = self.connector()
        db.save_message("fixture-a", "user", "count errors")
        self.assertEqual(db.get_history("fixture-a")[0][:2], ("user", "count errors"))
        self.assertEqual(db.get_history("fixture-b"), [])

    def test_alert_roundtrip_in_disposable_database(self):
        db = self.connector()
        conn = db._get_history_connection()
        try:
            conn.execute("INSERT INTO alerts (id, timestamp, severity, service, message, is_read) VALUES ('fixture', current_timestamp, 'info', 'fixture-service', 'synthetic', false)")
        finally:
            conn.close()
        self.assertEqual(len(db.get_alerts()), 1)
        db.mark_alert_read("fixture")
        self.assertEqual(db.get_alerts(), [])

    def test_network_blocked(self):
        with self.assertRaises(PermissionError):
            socket.socket()

    def test_subprocess_blocked(self):
        with self.assertRaises(PermissionError):
            subprocess.run(["/bin/echo", "must not execute"], check=True)

    def test_project_writes_blocked(self):
        with self.assertRaises(PermissionError):
            (ROOT / "isolation-probe-must-not-exist").write_text("blocked")

    def test_project_data_reads_blocked(self):
        with self.assertRaises(PermissionError):
            (ROOT / "data/target/logs.duckdb").open("rb")

    def test_scripted_external_boundaries(self):
        spec = importlib.util.spec_from_file_location("isolated_fakes", ROOT / "tests/isolated/fakes.py")
        fakes = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fakes)
        llm = fakes.ScriptedLLM(["sql", TimeoutError("synthetic outage")])
        self.assertEqual(llm.generate("classify"), "sql")
        with self.assertRaises(TimeoutError):
            llm.generate("synthesize")
        with self.assertRaises(AssertionError):
            llm.generate("unplanned retry")
        search = fakes.ScriptedSearch("synthetic result")
        self.assertEqual(search.search("fixture"), "synthetic result")
        self.assertEqual(search.calls, ["fixture"])
        self.assertIn("test fixture", (ROOT / "tests/isolated/fixtures/runbook.md").read_text())
