import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from services.pilot_orchestrator.src.graph import pilot_graph

def main():
    print("🚁 Pilot Orchestrator Ready! Type 'exit' to quit.")
    
    while True:
        user_input = input("\nUser: ")
        if user_input.lower() in ["exit", "quit"]:
            break
            
        # Initial State
        initial_state = {
            "query": user_input,
            "retry_count": 0,
            "history": []
        }
        
        print("Thinking...")
        try:
            # Invoke Graph
            result = pilot_graph.invoke(initial_state)
            print(f"🤖 Pilot: {result.get('final_answer')}")
            
            # Debug: Show path taken
            if result.get("intent") == "sql":
                print(f"   [Debug] SQL Executed: {result.get('sql_query')}")
            elif result.get("intent") == "rag":
                print(f"   [Debug] RAG Context: {result.get('rag_context')[:50]}...")
                
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
