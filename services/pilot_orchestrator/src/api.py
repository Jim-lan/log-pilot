import sys
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from services.pilot_orchestrator.src.graph import pilot_graph

app = FastAPI(title="LogPilot Orchestrator API", version="1.0.0")

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    answer: str
    sql: Optional[str] = None
    context: Optional[str] = None
    intent: str

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/query", response_model=QueryResponse)
def run_query(request: QueryRequest):
    """
    Executes the Pilot Agent for a given query.
    """
    try:
        # Initialize state
        initial_state = {"query": request.query, "messages": []}
        
        # Run the graph
        # invoke returns the final state
        final_state = pilot_graph.invoke(initial_state)
        
        return QueryResponse(
            answer=final_state.get("final_answer", "No answer generated."),
            sql=final_state.get("sql_query"),
            context=final_state.get("rag_context"),
            intent=final_state.get("intent", "unknown")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
