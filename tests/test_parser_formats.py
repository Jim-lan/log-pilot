import unittest
import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from shared.utils.log_parser import LogParser

class TestLogParser(unittest.TestCase):
    def setUp(self):
        self.parser = LogParser()

    def test_standard_format(self):
        log = "2025-11-24 10:00:00 INFO payment-service: Payment processed"
        parsed = self.parser.parse(log)
        self.assertEqual(parsed["severity"], "INFO")
        self.assertEqual(parsed["service_name"], "payment-service")
        self.assertEqual(parsed["body"], "Payment processed")
        self.assertEqual(parsed["timestamp"].year, 2025)

    def test_json_format(self):
        log = json.dumps({
            "timestamp": "2025-11-24T10:00:00Z",
            "level": "ERROR",
            "service": "auth-service",
            "message": "Login failed",
            "user_id": 123
        })
        parsed = self.parser.parse(log)
        self.assertEqual(parsed["severity"], "ERROR")
        self.assertEqual(parsed["service_name"], "auth-service")
        self.assertEqual(parsed["body"], "Login failed")
        self.assertEqual(parsed["context"]["user_id"], 123)

    def test_syslog_format(self):
        # Nov 24 16:00:00 myhost myservice[123]: message
        log = "Nov 24 16:00:00 ubuntu-server sshd[1234]: Accepted password for user root"
        parsed = self.parser.parse(log)
        self.assertEqual(parsed["service_name"], "sshd")
        self.assertEqual(parsed["body"], "Accepted password for user root")
        self.assertEqual(parsed["context"]["host"], "ubuntu-server")

    def test_nginx_format(self):
        # 127.0.0.1 - - [24/Nov/2025:16:00:00 +0000] "GET / HTTP/1.1" 200 123
        log = '192.168.1.1 - - [24/Nov/2025:16:00:00 +0000] "GET /api/v1/users HTTP/1.1" 200 1024'
        parsed = self.parser.parse(log)
        self.assertEqual(parsed["service_name"], "nginx")
        self.assertEqual(parsed["severity"], "INFO")
        self.assertIn("GET /api/v1/users", parsed["body"])
        self.assertEqual(parsed["context"]["status"], "200")

    def test_fallback_format(self):
        log = "This is just a random string that is not a log"
        parsed = self.parser.parse(log)
        self.assertEqual(parsed["severity"], "UNKNOWN")
        self.assertEqual(parsed["body"], "This is just a random string that is not a log")

if __name__ == "__main__":
    unittest.main()
