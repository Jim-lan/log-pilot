"""Real alert detection/persistence on deterministic UTC fixture windows."""
from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
import tempfile
import unittest

from services.sentry.src.main import SentryService


class SentryContracts(unittest.TestCase):
    def setUp(self):
        previous = Path.cwd()
        temporary = tempfile.TemporaryDirectory(dir=os.environ['LOGPILOT_TEST_SCRATCH'])
        self.addCleanup(temporary.cleanup)
        self.addCleanup(os.chdir, previous)
        os.chdir(temporary.name)
        self.clock = [datetime(2026, 9, 24, 12, tzinfo=timezone.utc).timestamp()]
        self.service = SentryService(clock=lambda: self.clock[0])

    def add(self, count, seconds_ago, severity='ERROR'):
        timestamp = datetime.fromtimestamp(self.clock[0], timezone.utc).replace(tzinfo=None) - timedelta(seconds=seconds_ago)
        with self.service.db._get_connection() as conn:
            conn.execute("INSERT INTO logs(timestamp,severity,service_name,body) SELECT ?,?,'fixture','synthetic' FROM range(?)",
                         [timestamp, severity, count])

    def test_quiet_expired_future_and_nonerror_logs_do_not_alert(self):
        self.add(20, 400)
        self.add(20, -1)
        self.add(20, 10, 'INFO')
        self.service.check_anomalies()
        self.assertEqual(self.service.db.get_alerts(), [])

    def test_spike_minimum_cooldown_and_dismissal(self):
        self.add(5, 10)
        self.service.check_anomalies()
        self.assertEqual(self.service.db.get_alerts(), [])
        self.add(1, 10)
        self.service.check_anomalies()
        alerts = self.service.db.get_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['service'], 'system')
        self.service.check_anomalies()
        self.assertEqual(len(self.service.db.get_alerts()), 1)
        self.service.db.mark_alert_read(alerts[0]['id'])
        self.assertEqual(self.service.db.get_alerts(), [])
        self.clock[0] += 61
        self.add(6, 10)
        self.service.check_anomalies()
        self.assertEqual(len(self.service.db.get_alerts()), 1)

    def test_ratio_and_window_boundaries_use_one_observation_time(self):
        self.add(100, 60)  # Exactly one minute old belongs to baseline, not current.
        self.add(500, 360)  # Exactly six minutes old is outside baseline.
        self.add(23, 0)  # Exactly now is included: 23 / 20 == threshold, no alert.
        self.service.check_anomalies()
        self.assertEqual(self.service.db.get_alerts(), [])
        self.add(1, 0)
        self.service.check_anomalies()
        self.assertEqual(len(self.service.db.get_alerts()), 1)
