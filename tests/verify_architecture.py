import sys
import os
import shutil
import json
from datetime import datetime

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from services.knowledge_base.src.store import KnowledgeStore
from shared.db.duckdb_client import DuckDBConnector
from shared.log_schema import LogEvent

def test_architecture():
    print("🧪 Starting Architecture Verification...")
    
    # Setup Temp Paths
    temp_vec_dir = "tests/temp_vector_store"
    temp_db_path = "tests/temp_logs.duckdb"
    
    if os.path.exists(temp_vec_dir):
        shutil.rmtree(temp_vec_dir)
    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)
        
    try:
        # 1. Initialize Stores
        print("🔹 Initializing Stores...")
        # Use a fresh embedding model instance or rely on global settings if set correctly in store.py
        # store.py sets Settings.embed_model globally on import.
        kb = KnowledgeStore(persist_dir=temp_vec_dir)
        db = DuckDBConnector(db_path=temp_db_path, read_only=False)
        
        # 2. Simulate Ingestion
        print("🔹 Simulating Ingestion...")
        
        # Pattern Event (goes to Chroma)
        template_str = "User <*> failed to login"
        cluster_id = "101"
        
        pattern_event = LogEvent(
            timestamp=datetime.now(),
            severity="INFO",
            service_name="auth-service",
            body=template_str,
            context={"cluster_id": cluster_id, "is_pattern": True}
        )
        kb.add_logs([pattern_event])
        
        # Log Event (goes to DuckDB)
        log_body = "User bob failed to login"
        log_event = {
            "timestamp": datetime.now(),
            "severity": "ERROR",
            "service_name": "auth-service",
            "trace_id": "abc-123",
            "body": log_body,
            "context": {"template_id": cluster_id, "user": "bob"}
        }
        db.insert_batch([log_event])
        
        # 3. Simulate Retrieval (The RAG Flow)
        print("🔹 Simulating Retrieval...")
        
        # Step A: Query Chroma for Pattern
        query = "login failure"
        nodes = kb.retrieve(query)
        
        found_id = None
        for node in nodes:
            print(f"   Found Node: {node.get_content()} | Metadata: {node.metadata}")
            # Note: Metadata keys might be converted to something else or kept as is.
            # LogConverter flattens context into metadata.
            if node.metadata.get("cluster_id") == cluster_id:
                found_id = node.metadata.get("cluster_id")
                break
        
        if not found_id:
            print("❌ Failed to retrieve pattern from ChromaDB")
            return
            
        print(f"✅ Retrieved Pattern ID: {found_id}")
        
        # Step B: Query DuckDB for Logs
        sql = f"SELECT body FROM logs WHERE json_extract_string(context, '$.template_id') = ?"
        logs = db.query(sql, [found_id])
        
        if not logs:
             print("❌ Failed to retrieve logs from DuckDB")
             return
             
        print(f"✅ Retrieved {len(logs)} logs from DuckDB")
        print(f"   Log Body: {logs[0][0]}")
        
        if logs[0][0] == log_body:
            print("🎉 SUCCESS: Architecture Verified!")
        else:
            print("❌ Log body mismatch")

    except Exception as e:
        print(f"❌ Test Failed with Exception: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        if os.path.exists(temp_vec_dir):
            shutil.rmtree(temp_vec_dir)
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)
            
if __name__ == "__main__":
    test_architecture()
