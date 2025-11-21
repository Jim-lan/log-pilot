import sys
import os
from typing import Dict, Any

# Add project root and service src paths to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../tool-service/src")))

from sql_gen import SQLGenerator
from rag_retriever import RAGRetriever

class LogPilotAgent:
    """
    The 'Brain' of the system. Routes user queries to the appropriate tool.
    """
    def __init__(self):
        self.sql_tool = SQLGenerator()
        self.rag_tool = RAGRetriever()

    def process_query(self, query: str) -> Dict[str, Any]:
        """
        Main entry point for user queries.
        Decides whether to use SQL (Data) or RAG (Knowledge).
        """
        print(f"\n🤖 Pilot received: '{query}'")
        
        # 1. Router Logic (Simple Keyword-based for Prototype)
        # In production, this would be an LLM Classifier
        
        intent = "unknown"
        # Check Knowledge Query first (Why/How to fix)
        if any(w in query.lower() for w in ["why", "cause", "fix", "solution", "similar", "root cause"]):
            intent = "knowledge_query"
        # Then check Data Query (Count/Show)
        elif any(w in query.lower() for w in ["count", "how many", "show", "list", "errors", "fail", "trend"]):
            intent = "data_query"
            
        # 2. Tool Execution
        if intent == "data_query":
            print("   👉 Routing to: SQL Generator (Data Plane)")
            results = self.sql_tool.execute(query)
            return {
                "intent": intent,
                "tool": "SQLGenerator",
                "result": results
            }
            
        elif intent == "knowledge_query":
            print("   👉 Routing to: RAG Retriever (Knowledge Plane)")
            results = self.rag_tool.retrieve(query)
            return {
                "intent": intent,
                "tool": "RAGRetriever",
                "result": results
            }
            
        else:
            return {
                "intent": "unknown",
                "message": "I didn't understand that. Try asking 'How many errors?' or 'Why is payment failing?'"
            }

if __name__ == "__main__":
    # Simple CLI Loop for testing
    agent = LogPilotAgent()
    print("🚁 LogPilot Agent Online. Type 'exit' to quit.")
    
    while True:
        user_input = input("\nUser > ")
        if user_input.lower() in ["exit", "quit"]:
            break
            
        response = agent.process_query(user_input)
        print(f"Agent > {response}")
