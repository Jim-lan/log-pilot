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

# --- File Watcher Imports ---
import glob
import shutil
from queue import Queue
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class LogFileHandler(FileSystemEventHandler):
    def __init__(self, queue, allowed_extensions=(".log",)):
        self.queue = queue
        self.allowed_extensions = allowed_extensions

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(self.allowed_extensions):
            print(f"👀 Detected new file: {event.src_path}")
            self.queue.put(event.src_path)

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.endswith(self.allowed_extensions):
             print(f"👀 Detected moved file: {event.dest_path}")
             self.queue.put(event.dest_path)

class FileWatcherConsumer:
    """Consumes logs from files in a directory using Watchdog."""
    def __init__(self, source_dir="data/source/landing_zone", processed_dir="data/source/processed"):
        self.source_dir = source_dir
        self.processed_dir = processed_dir
        self.file_queue = Queue()
        
        # Ensure directories exist
        os.makedirs(source_dir, exist_ok=True)
        os.makedirs(processed_dir, exist_ok=True)
        
        # 1. Scan existing files
        print(f"📂 Scanning {source_dir} for existing logs...")
        existing_files = sorted(glob.glob(os.path.join(source_dir, "*.log")))
        for f in existing_files:
            print(f"   -> Found existing: {f}")
            self.file_queue.put(f)
            
        # 2. Start Watchdog
        self.observer = Observer()
        handler = LogFileHandler(self.file_queue)
        self.observer.schedule(handler, source_dir, recursive=False)
        self.observer.start()
        print(f"👀 Watching for new logs in {source_dir}...")

    def __iter__(self):
        while True:
            # Block until a file is available? No, we need to respect the generator contract.
            # But the main loop expects an iterator that yields lines forever.
            
            if self.file_queue.empty():
                time.sleep(1) # Wait for files
                continue
                
            filepath = self.file_queue.get()
            filename = os.path.basename(filepath)
            processed_path = os.path.join(self.processed_dir, filename)
            
            # Handle duplicates/collisions in processed folder
            if os.path.exists(processed_path):
                base, ext = os.path.splitext(filename)
                ts = int(time.time())
                processed_path = os.path.join(self.processed_dir, f"{base}_{ts}{ext}")

            print(f"📖 Processing file: {filepath}")
            
            try:
                # wait slightly to ensure writing is done if it's being written to?
                # For this demo, we assume atomic moves or complete writes.
                time.sleep(0.5) 
                
                with open(filepath, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            yield line
                            
                # Move to processed
                print(f"✅ Finished {filename}, moving to processed.")
                try:
                    shutil.move(filepath, processed_path)
                except Exception as e:
                    print(f"⚠️ Failed to move file {filepath}: {e}")
                    
            except Exception as e:
                print(f"❌ Error reading file {filepath}: {e}")

class MockKafkaConsumer:
    """Simulates a Kafka Consumer yielding raw log lines."""
    def __init__(self):
        now = datetime.now().strftime("%Y-%m-%d")
        self.logs = [
            f"{now} 10:00:01 INFO payment-service: Payment processed for user_id=101 amount=50.00",
            f"{now} 10:00:02 ERROR auth-service: Login failed for user=admin ip=192.168.1.5 reason=bad_password",
            f"{now} 10:00:03 WARN db-service: Slow query detected on table=users duration=500ms",
            f"{now} 10:00:04 INFO payment-service: Payment processed for user_id=102 amount=25.00",
            f"{now} 10:00:05 ERROR auth-service: Login failed for user=guest ip=10.0.0.1 reason=locked_out",
            # PII Examples
            f"{now} 10:00:06 INFO email-service: Sending email to john.doe@example.com",
            f"{now} 10:00:07 INFO billing-service: Charging card 4111-1111-1111-1111 for $99.99"
        ]

    def __iter__(self):
        for log in self.logs:
            time.sleep(0.2) # Simulate network latency
            yield log

from shared.utils.template_miner import LogTemplateMiner



from shared.utils.log_parser import LogParser

from janitor import Janitor

class LogIngestor:
    def __init__(self):
        print("DEBUG: Initializing LogIngestor...")
        
        source_type = os.getenv("INGESTION_SOURCE", "MOCK").upper()
        if source_type == "FILE":
            print("DATA SOURCE: 📁 File Processor (Real-Time Watcher)")
            self.consumer = FileWatcherConsumer()
        else:
            print("DATA SOURCE: 🤖 Mock Generator (In-Memory)")
            self.consumer = MockKafkaConsumer()
            
        self.miner = LogTemplateMiner(persistence_file="data/state/drain3_state.bin")
        print("DEBUG: Initializing KnowledgeStore...")
        self.kb = KnowledgeStore() # ChromaDB (might download models)
        print("DEBUG: KnowledgeStore initialized.")
        self.db = DuckDBConnector() # Acquire DB lock ONLY after heavy init
        self.pii_masker = PIIMasker()
        self.parser = LogParser()
        self.janitor = Janitor(self.kb) # Initialize Janitor
        self.batch_size = 5
        self.batch_buffer = []
        self.log_event_buffer = [] # Buffer for LogEvent objects (needed for KB)

    def parse_log(self, raw_log: str) -> LogEvent:
        """Parses, masks, and enriches a raw log line."""
        # 1. Parse
        parsed = self.parser.parse(raw_log)
        
        # 2. Mask PII
        masked = self.pii_masker.mask_context(parsed)
        
        # 3. Mine Template
        mining_result = self.miner.mine_template(masked["body"])
        template_str = mining_result["template_mined"]
        cluster_id = mining_result["cluster_id"]
        change_type = mining_result["change_type"]
        
        # 4. Create LogEvent
        return LogEvent(
            timestamp=masked["timestamp"],
            severity=masked["severity"],
            service_name=masked["service_name"],
            body=masked["body"],
            # Map top-level optional fields
            department=masked.get("department"),
            environment=masked.get("environment"),
            host=masked.get("host"),
            region=masked.get("region"),
            context={
                "template_id": str(cluster_id), # Store ID as string
                "template_str": template_str,
                "change_type": change_type,
                **masked.get("context", {})
            }
        )

    def flush_batch(self):
        """Persists buffered logs to DuckDB and ChromaDB."""
        if not self.batch_buffer:
            return

        print(f"💾 Persisting batch of {len(self.batch_buffer)} logs...")
        
        # 1. DuckDB (Structured Data) - ALL LOGS
        try:
            self.db.insert_batch(self.batch_buffer)
        except Exception as e:
            print(f"❌ DuckDB Insert Failed: {e}")

        # 2. ChromaDB (Vector Data) - ONLY PATTERNS
        if self.log_event_buffer:
            try:
                print(f"🧠 Indexing {len(self.log_event_buffer)} new/updated patterns to ChromaDB...")
                self.kb.add_logs(self.log_event_buffer)
            except Exception as e:
                print(f"❌ ChromaDB Insert Failed: {e}")

        # Clear buffers
        self.batch_buffer = []
        self.log_event_buffer = []

    def run(self):
        print("🚀 Starting Ingestion Worker (Real-Time Mode)...")
        print("🔒 PII Masking Enabled")
        print("🗄️  DuckDB Persistence Enabled")
        print("🧠 ChromaDB Persistence Enabled (Pattern-Only Mode)")
        
        # Run Janitor at startup
        # Default retention: 30 days
        self.janitor.run_cleanup(retention_days=30)
        
        try:
            for raw_log in self.consumer:
                try:
                    event = self.parse_log(raw_log)
                    
                    # 1. Add to DuckDB Buffer (Always)
                    self.batch_buffer.append(event.model_dump())
                    
                    # 2. Add to ChromaDB Buffer (Only if Pattern Changed/Created)
                    change_type = event.context.get("change_type")
                    if change_type in ["cluster_created", "cluster_template_changed"]:
                        print(f"✨ New Pattern Discovered: {event.context['template_str']}")
                        # Create a Pattern LogEvent
                        pattern_event = LogEvent(
                            timestamp=event.timestamp,
                            severity=event.severity,
                            service_name=event.service_name,
                            body=event.context["template_str"], # Embed the PATTERN
                            context={
                                "cluster_id": event.context["template_id"],
                                "is_pattern": True
                            }
                        )
                        self.log_event_buffer.append(pattern_event)
                    
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

