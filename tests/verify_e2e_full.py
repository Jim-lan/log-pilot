import sys
import os
import shutil
import json
from datetime import datetime
from typing import Dict, Any

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from shared.db.duckdb_client import DuckDBConnector
from services.pilot_orchestrator.src.state import AgentState
from services.pilot_orchestrator.src.nodes import rewrite_query, classify_intent, generate_sql, validate_sql, execute_sql, retrieve_context, synthesize_answer
from shared.log_schema import LogEvent

def test_full_e2e():
    print("🧪 Starting Full E2E Verification...")
    
    # 1. Setup Temp Environment
    temp_db_path = "tests/temp_e2e.duckdb"
    temp_vec_dir = "tests/temp_e2e_vec"
    if os.path.exists(temp_db_path): os.remove(temp_db_path)
    if os.path.exists(temp_vec_dir): shutil.rmtree(temp_vec_dir)
    
    try:
        # 2. Initialize DB & Load Catalog
        print("\n🔹 Step 1: Initializing DB & Loading Catalog...")
        db = DuckDBConnector(db_path=temp_db_path, read_only=False)
        
        # Create Dummy Catalog
        with open("tests/temp_catalog.csv", "w") as f:
            f.write("service_name,department,criticality\n")
            f.write("user-service,Identity Team,High\n")
            f.write("payment-service,Billing Team,Critical\n")
            
        db.load_catalog("tests/temp_catalog.csv")
        
        # Verify Catalog Load
        cat_rows = db.query("SELECT * FROM system_catalog")
        print(f"   Catalog Rows: {cat_rows}")
        assert len(cat_rows) == 2, "Failed to load system catalog"
        
        # 3. Inject Dummy Logs
        print("\n🔹 Step 2: Injecting Logs...")
        db.insert_batch([
            {
                "timestamp": datetime.now(),
                "severity": "ERROR",
                "service_name": "payment-service",
                "body": "Connection timeout to gateway",
                "context": {"error_code": "504"}
            },
            {
                "timestamp": datetime.now(),
                "severity": "INFO",
                "service_name": "user-service",
                "body": "User login success",
                "context": {}
            }
        ])
        
        # 4. Test Query 1: System Catalog Join (WHO OWNS?)
        print("\n🔹 Step 3: Test SQL Agent (Catalog Join)...")
        state = AgentState(query="Who owns the payment-service?", messages=[])
        
        # Run Node Pipeline Manually (Rewrite -> Classify -> SQL -> Validate -> Execute)
        state = rewrite_query(state)
        state = classify_intent(state)
        print(f"   Intent: {state['intent']}")
        
        if state['intent'] == 'sql':
            state = generate_sql(state)
            print(f"   Generated SQL: {state.get('sql_query')}")
            state = validate_sql(state)
            if state.get('sql_valid'):
                state = execute_sql(state)
                print(f"   Result: {state.get('sql_result')}")
                state = synthesize_answer(state)
                print(f"   Answer: {state.get('final_answer')}")
            else:
                 print(f"   ❌ SQL Invalid: {state.get('sql_error')}")
        else:
             print("   ⚠️ Check Intent: Expected 'sql' for ownership query (or 'rag' if configured differently).")

        # 5. Test Query 2: Quantitative (COUNT)
        print("\n🔹 Step 4: Test SQL Agent (Count)...")
        state = AgentState(query="Count errors in payment-service", messages=[])
        state = rewrite_query(state)
        state = classify_intent(state)
        if state['intent'] == 'sql':
            state = generate_sql(state)
            state = validate_sql(state)
            if state.get('sql_valid'):
                state = execute_sql(state)
                # Should be 1
                res = state.get('sql_result')
                print(f"   Result: {res}")
                if "1" in str(res):
                    print("   ✅ Count Correct")
                else:
                    print("   ❌ Count Incorrect")
        
        print("\n✅ E2E Verification Completed WITHOUT CRASHES.")
        
    except Exception as e:
        print(f"\n❌ E2E Failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        if os.path.exists(temp_db_path): os.remove(temp_db_path)
        if os.path.exists("tests/temp_catalog.csv"): os.remove("tests/temp_catalog.csv")
        if os.path.exists(temp_vec_dir): shutil.rmtree(temp_vec_dir)

if __name__ == "__main__":
    test_full_e2e()
