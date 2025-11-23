import sys
import os
import pytest
# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from services.pilot_orchestrator.src.agent_legacy import LogPilotAgent

def test_agent():
    print("🧪 Starting Agent Verification...")
    agent = LogPilotAgent()
    
    test_cases = [
        ("Count all errors", "SQLGenerator"),
        ("How many failures in payment-service?", "SQLGenerator"),
        ("Why is the auth service failing?", "RAGRetriever"),
        ("What is the solution for timeout?", "RAGRetriever"),
        ("Hello world", "unknown")
    ]
    
    passed = 0
    for query, expected_tool in test_cases:
        print(f"\n❓ Query: '{query}'")
        response = agent.process_query(query)
        
        tool_used = response.get("tool", "unknown")
        if expected_tool == "unknown":
             if response.get("intent") == "unknown":
                 print("✅ Correctly identified as unknown.")
                 passed += 1
             else:
                 print(f"❌ Expected unknown, got {tool_used}")
        elif tool_used == expected_tool:
            print(f"✅ Correctly routed to {tool_used}")
            print(f"   Result: {response.get('result')}")
            passed += 1
        else:
            print(f"❌ Failed! Expected {expected_tool}, got {tool_used}")

    print(f"\n🎉 Verification Complete: {passed}/{len(test_cases)} passed.")

if __name__ == "__main__":
    test_agent()
