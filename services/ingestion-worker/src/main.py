import sys
import os
import time
import random
from datetime import datetime
from typing import Dict, Any

# Add project root to python path to allow importing shared modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shared.log_schema import LogEvent

class MockKafkaConsumer:
    """Simulates a Kafka Consumer yielding raw log lines."""
    def __init__(self):
        self.logs = [
            "2025-11-20 10:00:01 INFO payment-service: Payment processed for user_id=101 amount=50.00",
            "2025-11-20 10:00:02 ERROR auth-service: Login failed for user=admin ip=192.168.1.5 reason=bad_password",
            "2025-11-20 10:00:03 WARN db-service: Slow query detected on table=users duration=500ms",
            "2025-11-20 10:00:04 INFO payment-service: Payment processed for user_id=102 amount=25.00",
            "2025-11-20 10:00:05 ERROR auth-service: Login failed for user=guest ip=10.0.0.1 reason=locked_out"
        ]

    def __iter__(self):
        for log in self.logs:
            time.sleep(0.5) # Simulate network latency
            yield log

class MockDrain3:
    """Simulates Drain3 template mining."""
    def transform(self, content: str) -> str:
        # Simple heuristic for the prototype: mask numbers and IPs
        # In real Drain3, this is done via tree clustering
        template = content
        # Mask user_id
        if "user_id=" in template:
            parts = template.split("user_id=")
            template = parts[0] + "user_id=<*>" + " " + " ".join(parts[1].split(" ")[1:])
        # Mask amount
        if "amount=" in template:
             parts = template.split("amount=")
             template = parts[0] + "amount=<*>"
        # Mask user
        if "user=" in template:
            parts = template.split("user=")
            template = parts[0] + "user=<*>" + " " + " ".join(parts[1].split(" ")[1:])
        # Mask ip
        if "ip=" in template:
            parts = template.split("ip=")
            template = parts[0] + "ip=<*>" + " " + " ".join(parts[1].split(" ")[1:])
        
        return template.strip()

class LogIngestor:
    def __init__(self):
        self.consumer = MockKafkaConsumer()
        self.miner = MockDrain3()

    def parse_log(self, raw_log: str) -> LogEvent:
        # Simple parsing logic for the prototype
        parts = raw_log.split(" ")
        timestamp_str = f"{parts[0]} {parts[1]}"
        severity = parts[2]
        service_name = parts[3].replace(":", "")
        body = " ".join(parts[4:])
        
        # 1. Mine Template
        template = self.miner.transform(body)
        
        # 2. Extract Context (Naive extraction for prototype)
        context = {}
        for part in parts[4:]:
            if "=" in part:
                k, v = part.split("=")
                context[k] = v

        return LogEvent(
            timestamp=datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S"),
            severity=severity,
            service_name=service_name,
            body=template, # We store the TEMPLATE in the body, not the raw message
            context=context
        )

    def run(self):
        print("🚀 Starting Ingestion Worker (Prototype Mode)...")
        for raw_log in self.consumer:
            event = self.parse_log(raw_log)
            print(f"\n📥 Received: {raw_log}")
            print(f"✨ Processed LogEvent:")
            print(f"   ├── Timestamp: {event.timestamp}")
            print(f"   ├── Service:   {event.service_name}")
            print(f"   ├── Severity:  {event.severity}")
            print(f"   ├── Template:  {event.body}")
            print(f"   └── Context:   {event.context}")

if __name__ == "__main__":
    ingestor = LogIngestor()
    ingestor.run()
