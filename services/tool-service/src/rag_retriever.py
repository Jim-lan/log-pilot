from typing import List, Dict, Any

class RAGRetriever:
    """
    Retrieves similar logs or incidents using Vector Search.
    For the prototype, this returns Mock Data.
    """
    def __init__(self):
        # In real implementation, initialize ChromaDB client here
        pass

    def retrieve(self, query: str) -> List[Dict[str, Any]]:
        """
        Simulates retrieving similar past incidents based on semantic similarity.
        """
        print(f"🔍 Searching Knowledge Base for: '{query}'")
        
        # Mock Responses based on keywords
        if "payment" in query.lower():
            return [
                {
                    "id": "INC-001",
                    "summary": "Payment Gateway Timeout",
                    "root_cause": "Upstream provider API latency > 2s",
                    "resolution": "Retried transaction after 5s backoff.",
                    "similarity": 0.92
                }
            ]
        elif "auth" in query.lower() or "login" in query.lower():
             return [
                {
                    "id": "INC-002",
                    "summary": "Auth Service Rate Limiting",
                    "root_cause": "Redis cache full, evicting keys",
                    "resolution": "Scaled up Redis cluster.",
                    "similarity": 0.88
                }
            ]
            
        return [
            {
                "id": "DOC-101",
                "summary": "General Troubleshooting Guide",
                "root_cause": "N/A",
                "resolution": "Check system metrics (CPU/Memory).",
                "similarity": 0.5
            }
        ]
