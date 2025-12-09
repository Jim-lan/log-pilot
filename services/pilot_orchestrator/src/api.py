import sys
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from services.pilot_orchestrator.src.graph import pilot_graph

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="LogPilot Orchestrator API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for demo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    answer: str
    sql: Optional[str] = None
    context: Optional[str] = None
    intent: str

@app.get("/health")
def health_check():
    # Check LLM status
    from services.pilot_orchestrator.src.nodes import llm_client
    llm_status = llm_client.check_health()
    return {"status": "ok", "llm": llm_status}

@app.post("/query", response_model=QueryResponse)
def run_query(request: QueryRequest):
    """
    Executes the Pilot Agent for a given query.
    """
    try:
        # Fetch History for Context
        from services.pilot_orchestrator.src.nodes import sql_tool
        history_rows = sql_tool.db.get_history("default")
        # Format: [{"role": "user", "content": "..."}, ...]
        # Limit to last 10 messages to avoid context overflow
        messages = [{"role": row[0], "content": row[1]} for row in history_rows[-10:]]

        # Initialize state with history
        initial_state = {"query": request.query, "messages": messages}
        
        # Run the graph
        # invoke returns the final state
        final_state = pilot_graph.invoke(initial_state)
        
        answer = final_state.get("final_answer", "No answer generated.")
        
        # Save to History (Session ID = default for demo)
        try:
            from services.pilot_orchestrator.src.nodes import sql_tool
            # Save User Query
            sql_tool.db.save_message("default", "user", request.query)
            # Save AI Answer
            sql_tool.db.save_message("default", "ai", answer)
        except Exception as e:
            print(f"⚠️ Failed to save history: {e}")
        
        return QueryResponse(
            answer=answer,
            sql=final_state.get("sql_query"),
            context=final_state.get("rag_context"),
            intent=final_state.get("intent", "unknown")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history")
def get_chat_history():
    """
    Retrieves chat history for the default session.
    """
    try:
        from services.pilot_orchestrator.src.nodes import sql_tool
        history = sql_tool.db.get_history("default")
        # Format: [(role, content, timestamp), ...]
        return [{"role": row[0], "content": row[1], "timestamp": str(row[2])} for row in history]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
