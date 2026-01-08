import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

# Set Env Var for Local Testing BEFORE importing nodes
os.environ["LLM_BASE_URL"] = "http://localhost:11434/v1"

from services.pilot_orchestrator.src.nodes import rewrite_query
from services.pilot_orchestrator.src.state import AgentState

def test_rewrite_context_carryover():
    print("\n🧪 Testing Context Carryover...")
    
    # Scenario: User asked about errors in last 24h, now asks "which department?"
    state = AgentState(
        query="Which department has the most?",
        messages=[
            {"role": "user", "content": "How many errors in the last 24 hours?"},
            {"role": "assistant", "content": "There are 150 errors."}
        ],
        history=[],
        retry_count=0
    )
    
    # Mock LLM to inspect prompt
    with patch('services.pilot_orchestrator.src.nodes.llm_client') as mock_llm:
        # Set return value to simulate success (so we don't crash)
        mock_llm.generate.return_value = "Which department has the most errors in the last 24 hours?"
        
        # Invoke Node
        try:
            new_state = rewrite_query(state)
            rewritten = new_state.get("rewritten_query")
            
            print(f"Original: {state['query']}")
            print(f"Rewritten: {rewritten}")
            
            # Verify Prompt Content
            args, _ = mock_llm.generate.call_args
            prompt_sent = args[0]
            
            print("\n📝 Prompt Sent to LLM:")
            print("-" * 40)
            print(prompt_sent)
            print("-" * 40)
            
            # Check if history is in prompt
            if "How many errors in the last 24 hours?" in prompt_sent:
                print("✅ PASS: Chat history found in prompt.")
            else:
                print("❌ FAIL: Chat history MISSING from prompt.")
                
            # Check if instructions are in prompt
            if "Context Retention" in prompt_sent:
                 print("✅ PASS: New instructions found in prompt.")
            else:
                 print("❌ FAIL: New instructions MISSING from prompt.")

        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_rewrite_context_carryover()
