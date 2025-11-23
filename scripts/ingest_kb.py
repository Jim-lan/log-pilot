import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from services.knowledge_base.src.store import KnowledgeStore
from shared.db.duckdb_client import DuckDBConnector
from shared.log_schema import LogEvent

def ingest_kb():
    print("🧠 Starting Knowledge Base Ingestion...")
    
    # 1. Connect to DuckDB
    db = DuckDBConnector()
    
    # 2. Fetch logs (Limit to 200 for demo speed)
    print("   Fetching logs from DuckDB...")
    rows = db.query("SELECT * FROM logs LIMIT 200")
    
    if not rows:
        print("⚠️ No logs found in DuckDB. Run bulk loader first.")
        return

    # 3. Convert to LogEvents
    logs = []
    for row in rows:
        # Row format: (timestamp, severity, service_name, body, environment, app_id, department, host, region, trace_id, context)
        # Note: DuckDB returns tuples. We need to map them correctly.
        # Assuming schema order from DuckDBConnector._init_schema:
        # timestamp, severity, service_name, body, environment, app_id, department, host, region, trace_id, context
        
        try:
            context_str = row[10]
            context = json.loads(context_str) if context_str else {}
            
            event = LogEvent(
                timestamp=row[0],
                severity=row[1],
                service_name=row[2],
                body=row[3],
                environment=row[4],
                app_id=row[5],
                department=row[6],
                host=row[7],
                region=row[8],
                trace_id=row[9],
                context=context
            )
            logs.append(event)
        except Exception as e:
            print(f"   Skipping row due to error: {e}")

    # 4. Ingest into ChromaDB
    print(f"   Ingesting {len(logs)} logs into ChromaDB...")
    kb = KnowledgeStore()
    kb.add_logs(logs)
    
    print("✅ Knowledge Base Ingestion Complete!")

if __name__ == "__main__":
    ingest_kb()
