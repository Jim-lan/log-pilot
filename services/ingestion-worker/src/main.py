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
from shared.utils.pii_masker import PIIMasker
from services.knowledge_base.src.store import KnowledgeStore

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



from shared.utils.log_parser import LogParser

class LogIngestor:
    def __init__(self):
        self.consumer = MockKafkaConsumer()
        self.miner = LogTemplateMiner(persistence_file="data/state/drain3_state.bin")
        self.kb = KnowledgeStore() # ChromaDB (might download models)
        self.db = DuckDBConnector() # Acquire DB lock ONLY after heavy init
        self.pii_masker = PIIMasker()
        self.parser = LogParser()
        self.batch_size = 5
        self.batch_buffer = []
        self.log_event_buffer = [] # Buffer for LogEvent objects (needed for KB)

    def parse_log(self, raw_log: str) -> LogEvent:
        """
        Core Ingestion Pipeline:
        1. Parse: Normalize raw string -> Structured Dict (Timestamp, Severity, Service).
        2. Mask: Redact PII (Emails, IPs) from the body.
        3. Mine: Convert variable body -> Constant Template (Drain3).
        4. Context: Extract dynamic key-value pairs.
        """
        
        # Step 1: Robust Parsing
        # Uses the Strategy Pattern (JSON -> Regex -> Fallback) to handle any format.
        # Ensures 'timestamp' is always UTC.
        parsed = self.parser.parse(raw_log)
        
        # Step 2: PII Masking
        # We mask BEFORE mining templates to ensure sensitive data never enters the system.
        # e.g. "User 1.2.3.4 failed" -> "User <IP> failed"
        safe_body = self.pii_masker.mask_text(parsed["body"])
        
        # Step 3: Template Mining (Drain3)
        # Clusters similar logs to reduce noise.
        # e.g. "User <IP> failed" -> "User <*> failed"
        template = self.miner.mine_template(safe_body)
        
        # Step 4: Context Extraction
        # We preserve the original dynamic values in a JSON column.
        # If the log was JSON, we use that. Otherwise, we try to extract k=v pairs.
        context = parsed.get("context", {})
        if not context:
             # Simple heuristic for standard logs: look for k=v patterns
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
        
        print(f"💾 Flushing batch of {len(self.batch_buffer)} logs to DuckDB & ChromaDB...")
        try:
            # 1. Write to DuckDB (Structured)
            self.db.insert_batch(self.batch_buffer)
            
            # 2. Write to ChromaDB (Unstructured)
            self.kb.add_logs(self.log_event_buffer)
            
            # Clear buffers
            self.batch_buffer = []
            self.log_event_buffer = []
        except Exception as e:
            print(f"❌ Error flushing batch: {e}")

    def run(self):
        print("🚀 Starting Ingestion Worker (Real-Time Mode)...")
        print("🔒 PII Masking Enabled")
        print("🗄️  DuckDB Persistence Enabled")
        print("🧠 ChromaDB Persistence Enabled")
        
        try:
            for raw_log in self.consumer:
                try:
                    event = self.parse_log(raw_log)
                    
                    # Add to buffer
                    self.batch_buffer.append(event.model_dump())
                    self.log_event_buffer.append(event)
                    
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
            
            # Close connection to release lock
            self.db.close()

        except KeyboardInterrupt:
            print("\n🛑 Stopping worker...")
            self.flush_batch()
            self.db.close()

if __name__ == "__main__":
    ingestor = LogIngestor()
    ingestor.run()

