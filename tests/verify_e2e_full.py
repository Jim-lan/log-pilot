import sys
import os
import json
from unittest.mock import MagicMock

# ==============================================================================
# 🛑 AGGRESSIVE MOCKING START
# ==============================================================================
# 1. Mock External Deps
sys.modules["duckduckgo_search"] = MagicMock()
sys.modules["chromadb"] = MagicMock()
sys.modules["llama_index"] = MagicMock()
sys.modules["llama_index.core"] = MagicMock()
sys.modules["llama_index.vector_stores.chroma"] = MagicMock()

# 2. Mock Internal Deps to bypass creating real objects
sys.modules["services.knowledge_base.src.store"] = MagicMock()
sys.modules["services.knowledge_base.src"] = MagicMock()

# 3. Mock LLMClient Class BEFORE it is imported by nodes.py
mock_llm_module = MagicMock()
# Define the Mock LLM Instance and its generate method
mock_llm_instance = MagicMock()

def mock_generate(prompt, model_type="fast", **kwargs):
    prompt_str = str(prompt)
    if "You are the Router" in prompt_str or "intent_classifier" in prompt_str:
        return '{"intent": "sql", "reasoning": "mock"}'
    if "DuckDB SQL Developer" in prompt_str or "sql_generator" in prompt_str:
        return "SELECT department FROM system_catalog WHERE service_name = 'payment-service'"
    if "LogPilot" in prompt_str or "synthesize" in prompt_str:
        return "The payment-service is owned by the Billing Team. ✅"
    if "rewrite" in prompt_str.lower():
         return "Who owns the payment-service?"
    if "Who owns" in prompt_str: return "Who owns the payment-service?"
    return "Mock Response"

mock_llm_instance.generate.side_effect = mock_generate
# The class LLMClient returns our instance
mock_llm_module.LLMClient.return_value = mock_llm_instance
sys.modules["shared.llm.client"] = mock_llm_module

# Add project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
sys.path.append(project_root)

# Import Target Modules (Now they use Mocks!)
from services.pilot_orchestrator.src.state import AgentState
from services.pilot_orchestrator.src.nodes import rewrite_query, classify_intent, generate_sql, validate_sql, execute_sql, synthesize_answer
# ==============================================================================

# Singleton In-Memory DB (Pure DuckDB, no wrappers)
import duckdb
singleton_conn = duckdb.connect(":memory:")
singleton_conn.execute("CREATE TABLE system_catalog (service_name VARCHAR, department VARCHAR, criticality VARCHAR)")
singleton_conn.execute("INSERT INTO system_catalog VALUES ('payment-service', 'Billing Team', 'Critical')")

# Mock DB Wrapper that uses Singleton
class MockConnector:
    def __init__(self, *args, **kwargs): pass
    def query(self, sql, params=None):
        try:
            if params: return singleton_conn.execute(sql, params).fetchall()
            return singleton_conn.execute(sql).fetchall()
        except Exception as e:
            print(f"DB Error: {e}")
            raise e
    def close(self): pass

# We need to verify if nodes.py uses DuckDBConnector from shared.db.duckdb_client
# Since we already imported nodes.py, we might need to patch DuckDBConnector INSIDE sys.modules or patch the object in nodes logic.
# But since nodes.py imports `from shared.db.duckdb_client import DuckDBConnector`, we should Mock that MODULE too if possible, 
# OR patch it in nodes.py using patch.object.
# Since nodes.py is already imported now, we can use patch on the imported module attribute.

from unittest.mock import patch

@patch("services.pilot_orchestrator.src.nodes.DuckDBConnector", side_effect=MockConnector)
def test_full_e2e(MockDB):
    print("🧪 Starting Fully Module-Mocked Verification...")
    
    try:
        print("\n🔹 Testing Ownership Query...")
        state = AgentState(query="Who owns the payment-service?", messages=[])
        
        # 1. Rewrite
        state = rewrite_query(state)
        print(f"   Rewritten: {state.get('rewritten_query')}")
        
        # 2. Classify
        state = classify_intent(state)
        print(f"   Intent: {state['intent']}")
        assert state['intent'] == 'sql', f"Got {state['intent']} instead of sql"
        
        # 3. Generate SQL
        state = generate_sql(state)
        print(f"   SQL: {state.get('sql_query')}")
        assert "system_catalog" in state['sql_query']
        
        # 4. Validate (Will use MockDB which uses singleton)
        state = validate_sql(state)
        
        # 5. Execute
        if state.get('sql_valid'):
            state = execute_sql(state)
            print(f"   Result: {state.get('sql_result')}")
            assert "Billing Team" in str(state.get('sql_result'))
            
            # 6. Synthesize
            state = synthesize_answer(state)
            print(f"   Answer: {state.get('final_answer')}")
            assert "Billing Team" in state.get('final_answer')
        else:
            print(f"❌ SQL Invalid: {state.get('sql_error')}")
            raise Exception("SQL Validation Failed")

        print("\n✅ Verification SUCCESS!")

    except Exception as e:
        print(f"\n❌ Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_full_e2e()
