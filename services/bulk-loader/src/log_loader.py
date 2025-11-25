import sys
import os
import time
import random
import json
import argparse
from datetime import datetime, timedelta
from typing import List

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shared.log_schema import LogEvent
from shared.db.duckdb_client import DuckDBConnector
from shared.utils.log_parser import LogParser
from shared.utils.template_miner import LogTemplateMiner
from shared.utils.pii_masker import PIIMasker

class BulkLoaderJob:
    def __init__(self):
        self.db = DuckDBConnector()
        self.miner = LogTemplateMiner(persistence_file="data/state/drain3_state.bin")
        self.parser = LogParser()
        self.pii_masker = PIIMasker()

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
                        # 1. Parse (Multi-Format)
                        parsed = self.parser.parse(line)
                        
                        # 2. Mask PII
                        safe_body = self.pii_masker.mask_text(parsed["body"])
                        
                        # 3. Mine Template
                        template = self.miner.mine_template(safe_body)
                        
                        # 4. Extract Context
                        context = parsed.get("context", {})
                        context["source_file"] = filename
                        
                        # Extract standard metadata from context if present
                        environment = context.get("environment") or context.get("env")
                        app_id = context.get("app_id")
                        department = context.get("department") or context.get("dept")
                        host = context.get("host")
                        region = context.get("region")

                        event = LogEvent(
                            timestamp=parsed["timestamp"],
                            severity=parsed["severity"],
                            service_name=parsed["service_name"],
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
                        print(f"\n⚠️ Error processing line: {line[:50]}... -> {e}")
                        continue

            # Insert remaining
            if batch:
                self.db.insert_batch(batch)
            print("\n")
            
        except FileNotFoundError:
            print(f"❌ File not found: {file_path}")

    def run(self, landing_zone: str = "data/source/landing_zone"):
        print(f"🚀 Starting Phase 1: Bulk Loader Job (Scanning {landing_zone})")
        
        if not os.path.exists(landing_zone):
            print(f"❌ Landing zone {landing_zone} does not exist.")
            return

        files = [f for f in os.listdir(landing_zone) if f.endswith(".log")]
        if not files:
            print(f"⚠️ No .log files found in {landing_zone}.")
            return

        for filename in files:
            file_path = os.path.join(landing_zone, filename)
            self.process_file(file_path)
        
        # Save Miner State
        print("💾 Saving Template Miner State...")
        self.miner.save_state()
        
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
    parser = argparse.ArgumentParser(description="Bulk load logs into DuckDB.")
    parser.add_argument("--landing_zone", type=str, default="data/source/landing_zone", help="Directory containing log files.")
    args = parser.parse_args()
    
    job = BulkLoaderJob()
    job.run(landing_zone=args.landing_zone)
