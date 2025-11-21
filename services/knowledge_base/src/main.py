import sys
import os
from datetime import datetime

# Add project root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from services.knowledge_base.src.store import KnowledgeStore
from shared.log_schema import LogEvent

def main():
    print("🧠 Starting Knowledge Base Service...")
    
    # Initialize Store
    kb = KnowledgeStore()
    
    # Sample Data
    sample_logs = [
        LogEvent(
            timestamp=datetime.now(),
            severity="ERROR",
            service_name="auth-service",
            body="Login failed for user=admin ip=192.168.1.5",
            context={"user": "admin", "ip": "192.168.1.5"}
        ),
        LogEvent(
            timestamp=datetime.now(),
            severity="INFO",
            service_name="payment-service",
            body="Payment processed successfully for order=123",
            context={"order_id": "123"}
        )
    ]
    
    # Ingest
    print("📥 Ingesting sample logs...")
    kb.add_logs(sample_logs)
    
    # Query Loop
    print("\n💬 Knowledge Base Ready! Type 'exit' to quit.")
    while True:
        query = input("\nQuery: ")
        if query.lower() in ["exit", "quit"]:
            break
        
        try:
            response = kb.query(query)
            print(f"🤖 Answer: {response}")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
