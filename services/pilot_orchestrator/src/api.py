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
    sql_result: Optional[str] = None
    context: Optional[str] = None
    intent: str
    metadata: Optional[Dict[str, Any]] = {}



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
        import time
        start_time = time.time()
        print("DEBUG: Fetching History...")
        # Fetch History for Context
        from shared.db.duckdb_client import DuckDBConnector
        # Use a fresh connector for history operations
        print("DEBUG: Initializing DuckDBConnector...")
        db = DuckDBConnector(read_only=False) 
        print("DEBUG: DuckDBConnector initialized.")
        
        history_rows = db.get_history("default")
        print(f"DEBUG: History fetched: {len(history_rows)} rows.")
        # Format: [{"role": "user", "content": "..."}, ...]
        # Limit to last 10 messages to avoid context overflow
        messages = [{"role": row[0], "content": row[1]} for row in history_rows[-10:]]
        
        # Close DB to release lock before graph execution
        db.close()
        print("DEBUG: DB closed to release lock.")

        # Initialize state with history
        initial_state = {"query": request.query, "messages": messages}
        
        # Run the graph
        # invoke returns the final state
        final_state = pilot_graph.invoke(initial_state)
        
        answer = final_state.get("final_answer", "No answer generated.")
        
        # Save to History (Session ID = default for demo)
        try:
            # Re-open DB for saving
            db = DuckDBConnector(read_only=False)
            # Save User Query
            db.save_message("default", "user", request.query)
            # Save AI Answer
            db.save_message("default", "ai", answer)
            db.close() # Close connection
        except Exception as e:
            print(f"⚠️ Failed to save history: {e}")
        
        latency = time.time() - start_time
        
        return QueryResponse(
            answer=answer,
            sql=final_state.get("sql_query"),
            sql_result=final_state.get("sql_result"),
            context=final_state.get("rag_context"),
            intent=final_state.get("intent", "unknown"),
            metadata={
                "rewritten_query": final_state.get("rewritten_query"),
                "latency": latency,
                "context_feedback": final_state.get("context_feedback"),
                "answer_feedback": final_state.get("answer_feedback")
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history")
def get_chat_history():
    """
    Retrieves chat history for the default session.
    """
    try:
        from shared.db.duckdb_client import DuckDBConnector
        db = DuckDBConnector(read_only=True)
        history = db.get_history("default")
        db.close()
        # Format: [(role, content, timestamp), ...]
        return [{"role": row[0], "content": row[1], "timestamp": str(row[2])} for row in history]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
def get_metrics():
    """
    Retrieves evaluation metrics from the metrics database.
    """
    try:
        import duckdb
        db_path = "data/target/metrics.duckdb"
        
        if not os.path.exists(db_path):
            return {
                "pass_rate_24h": 0,
                "avg_latency_24h": 0,
                "total_runs": 0,
                "history": []
            }

        conn = duckdb.connect(db_path, read_only=True)
        
        # 1. Pass Rate (Last 24h) - aggregating from eval_runs
        # Note: In a real app, we'd filter by timestamp > now() - interval '24 hours'
        # For demo, we just take the average of all runs
        pass_rate = conn.execute("SELECT AVG(pass_rate) FROM eval_runs").fetchone()[0] or 0
        
        # 2. Average Latency (Last 24h) - aggregating from eval_results
        avg_latency = conn.execute("SELECT AVG(latency) FROM eval_results").fetchone()[0] or 0
        
        # 3. Total Runs
        total_runs = conn.execute("SELECT COUNT(*) FROM eval_runs").fetchone()[0] or 0
        
        # 4. History for Chart (Last 10 runs)
        history = conn.execute("""
            SELECT run_id, timestamp, pass_rate 
            FROM eval_runs 
            ORDER BY timestamp DESC 
            LIMIT 10
        """).fetchall()
        
        conn.close()
        
        return {
            "pass_rate_24h": round(pass_rate, 1),
            "avg_latency_24h": round(avg_latency, 2),
            "total_runs": total_runs,
            "history": [{"run_id": h[0], "timestamp": str(h[1]), "pass_rate": h[2]} for h in history]
        }
    except Exception as e:
        print(f"❌ Metrics Error: {e}")
        return {
            "pass_rate_24h": 0,
            "avg_latency_24h": 0,
            "total_runs": 0,
            "history": []
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
