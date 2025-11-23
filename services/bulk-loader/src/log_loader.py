import sys
import os
import time
import random
import json
from datetime import datetime, timedelta
from typing import List

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shared.log_schema import LogEvent
from shared.db.duckdb_client import DuckDBConnector

class MockDrain3:
    """Simulates Drain3 template mining (Reused from prototype)."""
    def transform(self, content: str) -> str:
        template = content
        if "user_id=" in template:
            parts = template.split("user_id=")
            template = parts[0] + "user_id=<*>" + " " + " ".join(parts[1].split(" ")[1:])
        if "amount=" in template:
             parts = template.split("amount=")
             template = parts[0] + "amount=<*>"
        if "user=" in template:
            parts = template.split("user=")
            template = parts[0] + "user=<*>" + " " + " ".join(parts[1].split(" ")[1:])
        if "ip=" in template:
            parts = template.split("ip=")
            template = parts[0] + "ip=<*>" + " " + " ".join(parts[1].split(" ")[1:])
        return template.strip()

class BulkLoaderJob:
    def __init__(self):
        self.db = DuckDBConnector()
        self.miner = MockDrain3()

    def process_file(self, file_path: str):
        """Reads a log file and loads it into DuckDB."""
        filename = os.path.basename(file_path)
        print(f"📄 Processing file: {filename}")
        
        batch_size = 100
        batch = []
        
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        # Parse (Simple logic reused from prototype)
                        # Expected Format: YYYY-MM-DD HH:MM:SS SEVERITY SERVICE: MESSAGE
                        parts = line.split(" ")
                        if len(parts) < 4:
                            continue # Skip malformed lines

                        timestamp_str = f"{parts[0]} {parts[1]}"
                        severity = parts[2]
                        service_name = parts[3].replace(":", "")
                        body = " ".join(parts[4:])
                        
                        # Mine Template
                        template = self.miner.transform(body)
                        
                        # Extract Context
                        context = {"source_file": filename} # Add metadata
                        for part in parts[4:]:
                            if "=" in part:
                                k, v = part.split("=")
                                context[k] = v
                        
                        # Extract standard metadata from context if present
                        environment = context.get("environment") or context.get("env")
                        app_id = context.get("app_id")
                        department = context.get("department") or context.get("dept")
                        host = context.get("host")
                        region = context.get("region")

                        event = LogEvent(
                            timestamp=datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S"),
                            severity=severity,
                            service_name=service_name,
                            body=template,
                            environment=environment,
                            app_id=app_id,
                            department=department,
                            host=host,
                            region=region,
                            context=context
                        )
                        
                        batch.append(event.model_dump())
                        
                        if len(batch) >= batch_size:
                            self.db.insert_batch(batch)
                            batch = []
                            sys.stdout.write(".")
                            sys.stdout.flush()
                    except Exception as e:
                        print(f"\n⚠️ Error processing line: {line} -> {e}")
                        continue

            # Insert remaining
            if batch:
                self.db.insert_batch(batch)
            print("\n")
            
        except FileNotFoundError:
            print(f"❌ File not found: {file_path}")

    def run(self, landing_zone: str = "data/landing_zone"):
        print(f"🚀 Starting Phase 1: Bulk Loader Job (Scanning {landing_zone})")
        
        if not os.path.exists(landing_zone):
            print(f"❌ Landing zone {landing_zone} does not exist.")
            return

        files = [f for f in os.listdir(landing_zone) if f.endswith(".log")]
        if not files:
            print("⚠️ No .log files found in landing zone.")
            return

        for filename in files:
            file_path = os.path.join(landing_zone, filename)
            self.process_file(file_path)
        
        # Verify
        count = self.db.query("SELECT count(*) FROM logs")[0][0]
        print(f"✅ Total logs in DuckDB: {count}")
        
        print("🔍 Sample JSON Query (Source File Distribution):")
        results = self.db.query("""
            SELECT context->>'source_file' as file, count(*) as count
            FROM logs 
            GROUP BY 1
            ORDER BY 2 DESC
        """)
        for row in results:
            print(f"   File: {row[0]}, Count: {row[1]}")

if __name__ == "__main__":
    job = BulkLoaderJob()
    job.run()
