import sys
import os
import time
import random
from datetime import datetime
from typing import Dict, Any, List

# Add project root to python path to allow importing shared modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shared.log_schema import LogEvent
from shared.db.duckdb_client import DuckDBConnector
from shared.utils import PIIMasker

class MockKafkaConsumer:
    """Simulates a Kafka Consumer yielding raw log lines."""
    def __init__(self):
        self.logs = [
            "2025-11-20 10:00:01 INFO payment-service: Payment processed for user_id=101 amount=50.00",
            "2025-11-20 10:00:02 ERROR auth-service: Login failed for user=admin ip=192.168.1.5 reason=bad_password",
            "2025-11-20 10:00:03 WARN db-service: Slow query detected on table=users duration=500ms",
            "2025-11-20 10:00:04 INFO payment-service: Payment processed for user_id=102 amount=25.00",
            "2025-11-20 10:00:05 ERROR auth-service: Login failed for user=guest ip=10.0.0.1 reason=locked_out",
            # PII Examples
            "2025-11-20 10:00:06 INFO email-service: Sending email to john.doe@example.com",
            "2025-11-20 10:00:07 INFO billing-service: Charging card 4111-1111-1111-1111 for $99.99"
        ]

    def __iter__(self):
        for log in self.logs:
            time.sleep(0.2) # Simulate network latency
            yield log

from shared.utils.template_miner import LogTemplateMiner

class MockSchemaRegistry:
    """
    (Deprecated) Replaced by LogTemplateMiner.
    Keeping class for reference if needed, but logic is now in shared/utils/template_miner.py
    """
    pass

from shared.utils.log_parser import LogParser

class LogIngestor:
    def __init__(self):
        self.consumer = MockKafkaConsumer()
        self.miner = LogTemplateMiner(persistence_file="data/drain3_state.bin")
        self.db = DuckDBConnector()
        self.pii_masker = PIIMasker()
        self.parser = LogParser()
        self.batch_size = 5
        self.batch_buffer = []

    def parse_log(self, raw_log: str) -> LogEvent:
        # 1. Robust Regex Parsing + UTC Normalization
        parsed = self.parser.parse(raw_log)
        
        # 2. Mask PII in the body immediately
        safe_body = self.pii_masker.mask_text(parsed["body"])
        
        # 3. Get Template (Drain3)
        template = self.miner.mine_template(safe_body)
        
        # 4. Extract Context (Simple Key-Value extraction from body)
        context = {}
        # Simple heuristic: look for k=v patterns in the message
        for part in safe_body.split(" "):
            if "=" in part:
                try:
                    k, v = part.split("=", 1)
                    context[k] = v
                except ValueError:
                    pass

        return LogEvent(
            timestamp=parsed["timestamp"],
            severity=parsed["severity"],
            service_name=parsed["service_name"],
            body=template, 
            context=context
        )

    def flush_batch(self):
        if not self.batch_buffer:
            return
        
        print(f"💾 Flushing batch of {len(self.batch_buffer)} logs to DuckDB...")
        try:
            self.db.insert_batch(self.batch_buffer)
            self.batch_buffer = []
        except Exception as e:
            print(f"❌ Error flushing batch: {e}")

    def run(self):
        print("🚀 Starting Ingestion Worker (Real-Time Mode)...")
        print("🔒 PII Masking Enabled")
        print("🗄️  DuckDB Persistence Enabled")
        
        try:
            for raw_log in self.consumer:
                try:
                    event = self.parse_log(raw_log)
                    
                    # Add to buffer
                    self.batch_buffer.append(event.model_dump())
                    
                    print(f"✅ Processed: {event.timestamp} [{event.service_name}] {event.body}")
                    
                    if len(self.batch_buffer) >= self.batch_size:
                        self.flush_batch()
                        
                except Exception as e:
                    print(f"⚠️ Failed to process log: {raw_log} -> {e}")
            
            # Flush remaining
            self.flush_batch()
            
            # Verification Query
            print("\n🔎 Verifying Data in DuckDB:")
            count = self.db.query("SELECT count(*) FROM logs")[0][0]
            print(f"   Total Rows: {count}")
            
            print("   Sample Rows (Check PII Masking):")
            samples = self.db.query("SELECT body, context FROM logs ORDER BY timestamp DESC LIMIT 3")
            for row in samples:
                print(f"   - Body: {row[0]}")
                print(f"   - Context: {row[1]}")

        except KeyboardInterrupt:
            print("\n🛑 Stopping worker...")
            self.flush_batch()
            self.db.close()

if __name__ == "__main__":
    ingestor = LogIngestor()
    ingestor.run()

