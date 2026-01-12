import sys
import os
import time
import threading
import json
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

# --- MOCK EVERYTHING BEFORE IMPORTS ---
sys.modules["duckduckgo_search"] = MagicMock()
sys.modules["chromadb"] = MagicMock()
sys.modules["chromadb.api"] = MagicMock() # Fix for "not a package"

# Mock internal modules to avoid loading them
sys.modules["services.knowledge_base.src.store"] = MagicMock()
sys.modules["services.pilot_orchestrator.src.tools.sql_tool"] = MagicMock()
sys.modules["services.pilot_orchestrator.src.tools.web_search"] = MagicMock()
sys.modules["janitor"] = MagicMock()
sys.modules["watchdog"] = MagicMock()
sys.modules["watchdog.observers"] = MagicMock()
sys.modules["watchdog.events"] = MagicMock()


# Mock DB Client
sys.modules["shared.db.duckdb_client"] = MagicMock() 
mock_db_connector = MagicMock()
mock_db_instance = MagicMock()
mock_db_connector.return_value = mock_db_instance
mock_db_instance.get_history.return_value = [] 
sys.modules["shared.db.duckdb_client"].DuckDBConnector = mock_db_connector

# Mock LLMClient
mock_llm_client = MagicMock()
sys.modules["shared.llm.client"] = MagicMock()
sys.modules["shared.llm.client"].LLMClient.return_value = mock_llm_client

# Now we can import api safely (hopefully)
try:
    from services.pilot_orchestrator.src.api import app
except ImportError as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)

from fastapi.testclient import TestClient

# --- Test 1: Pilot API Metadata ---
def test_pilot_api_metadata():
    print("\n🧪 Testing Pilot API Metadata...")
    try:
        client = TestClient(app)
        
        # Patch the graph invocation
        mock_state = {
            "final_answer": "Mock Answer",
            "sql_query": "SELECT * FROM logs",
            "rag_context": "Mock Context",
            "intent": "sql",
            "rewritten_query": "Rewritten Query",
            "context_feedback": "Good",
            "answer_feedback": "Valid"
        }
        
        # We need to patch where it is used.
        # api.py imports pilot_graph from services.pilot_orchestrator.src.graph
        # So we patch that object
        with patch("services.pilot_orchestrator.src.graph.pilot_graph.invoke", return_value=mock_state):
             # Ensure DB connector is mocked during the call (runtime import)
             # Our sys.modules hack *should* handle it.
            response = client.post("/query", json={"query": "test"})
            
            if response.status_code != 200:
                print(f"❌ API Call Failed: {response.text}")
                return False
                
            data = response.json()
            print(f"   Response Keys: {data.keys()}")
            
            if "metadata" not in data:
                print("❌ 'metadata' field missing in response!")
                return False
                
            metadata = data["metadata"]
            print(f"   Metadata: {metadata}")
            
            if "latency" not in metadata:
                print("❌ 'latency' missing in metadata!")
                return False
                
            if metadata["rewritten_query"] != "Rewritten Query":
                print("❌ 'rewritten_query' incorrect!")
                return False
                
            print("✅ API Metadata Verified.")
            return True
                
    except Exception as e:
        print(f"❌ API Test Exception: {e}")
        import traceback
        traceback.print_exc()
        return False
        
from unittest.mock import patch

# --- Test 2: Ingestion File Stability ---
def test_ingestion_stability():
    print("\n🧪 Testing Ingestion File Stability...")
    
    # We need to import main.py from ingestion worker.
    # But it imports shared modules too. Since we mocked them globally in sys.modules, it should be fine!
    
    # Dynamic import
    import importlib.util
    spec = importlib.util.spec_from_file_location("ingestion_main", "services/ingestion-worker/src/main.py")
    ingestor_mod = importlib.util.module_from_spec(spec)
    sys.modules["services.ingestion-worker.src.main"] = ingestor_mod # register it
    try:
        spec.loader.exec_module(ingestor_mod)
    except Exception as e:
        print(f"❌ Failed to load ingestion module: {e}")
        return False
    
    FileWatcherConsumer = ingestor_mod.FileWatcherConsumer
    
    # Create a dummy class
    class TestConsumer(FileWatcherConsumer):
        def __init__(self):
            # Bypass init that uses observers
            pass
            
    consumer = TestConsumer()
    
    test_file = "test_stability.tmp"
    
    # 1. Stable file
    with open(test_file, "w") as f:
        f.write("data")
    time.sleep(1) 
    
    print("   Testing Stable File...")
    if not consumer._wait_for_file_stability(test_file, timeout=2):
        print("❌ Failed to detect stable file.")
        if os.path.exists(test_file): os.remove(test_file)
        return False
    print("   ✅ Stable file detected.")
    
    # 2. Unstable file
    print("   Testing Unstable File...")
    stop_writing = False
    
    def background_writer():
        for i in range(10):
            if stop_writing: break
            with open(test_file, "a") as f:
                f.write(".")
            time.sleep(0.2)
            
    t = threading.Thread(target=background_writer)
    t.start()
    
    # Timeout 1s, writer runs 2s
    is_stable = consumer._wait_for_file_stability(test_file, timeout=1.0)
    stop_writing = True
    t.join()
    
    if is_stable:
        print("❌ Incorrectly identified growing file as stable!")
        if os.path.exists(test_file): os.remove(test_file)
        return False
    else:
        print("   ✅ correctly rejected unstable file (timeout).")
        
    if os.path.exists(test_file):
        os.remove(test_file)
        
    return True

if __name__ == "__main__":
    success = True
    success &= test_pilot_api_metadata()
    success &= test_ingestion_stability()
    
    if success:
        print("\n🎉 ALL TESTS PASSED")
    else:
        print("\n💥 TESTS FAILED")
        sys.exit(1)
