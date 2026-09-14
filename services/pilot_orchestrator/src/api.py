import sys
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
from shared.execution import RequestBudget, ExecutionFailure, DeadlineExceeded, use_budget, setting
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from services.pilot_orchestrator.src.graph import pilot_graph

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="LogPilot Orchestrator API", version="1.0.0")
query_workers = setting("LOGPILOT_QUERY_WORKERS", 4, int)
query_executor = ThreadPoolExecutor(max_workers=query_workers, thread_name_prefix="pilot-query")
query_slots = threading.BoundedSemaphore(query_workers)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for demo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str
    persist_history: bool = True

class QueryResponse(BaseModel):
    answer: str
    sql: Optional[str] = None
    sql_result: Optional[str] = None
    sql_rows: Optional[List[List[Any]]] = None
    context: Optional[str] = None
    intent: str
    metadata: Optional[Dict[str, Any]] = {}
    trace: Optional[List[Dict[str, Any]]] = None

@app.get("/health")
def health_check():
    # Check LLM status
    from services.pilot_orchestrator.src.nodes import llm_client
    llm_status = llm_client.check_health()
    return {"status": "ok", "llm": llm_status}

@app.post("/query", response_model=QueryResponse)
async def run_query(request: QueryRequest):
    budget = RequestBudget.from_env()
    if not query_slots.acquire(blocking=False):
        raise HTTPException(status_code=503, detail={"code": "query_capacity_exhausted",
                                                     "message": "All query workers are busy. Please retry later."})

    def work():
        try:
            with use_budget(budget):
                return _run_query(request, budget)
        finally:
            # A timeout does not free capacity until the synchronous work stops.
            query_slots.release()

    try:
        future = asyncio.get_running_loop().run_in_executor(query_executor, work)
    except Exception:
        query_slots.release()
        raise
    future.add_done_callback(lambda completed: completed.exception() if not completed.cancelled() else None)
    try:
        return await asyncio.wait_for(asyncio.shield(future), timeout=budget.remaining())
    except asyncio.TimeoutError:
        budget.cancel()
        failure = DeadlineExceeded()
        raise HTTPException(status_code=failure.status, detail={"code": failure.code, "message": failure.message})
    except ExecutionFailure as failure:
        raise HTTPException(status_code=failure.status, detail={"code": failure.code, "message": failure.message})
    except asyncio.CancelledError:
        budget.cancel()
        raise


def _run_query(request: QueryRequest, budget: RequestBudget):
    """
    Executes the Pilot Agent for a given query.
    """
    try:
        import time
        start_time = time.time()
        budget.check()
        print("DEBUG: Fetching History...")
        # Fetch History for Context
        from shared.db.duckdb_client import DuckDBConnector
        # Use a fresh connector for history operations
        print("DEBUG: Initializing DuckDBConnector...")
        # Use read_only=True to avoid locking logs.duckdb (Ingestion Worker is the writer)
        # History operations manage their own connection to history.duckdb
        db = DuckDBConnector(read_only=True) 
        print("DEBUG: DuckDBConnector initialized.")
        
        history_rows = db.get_history("default") if request.persist_history else []
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
        budget.check()
        
        answer = final_state.get("final_answer", "No answer generated.")
        
        # Save to History (Session ID = default for demo)
        try:
            # Re-open DB for saving (read_only=True is fine, history connection is separate)
            db = DuckDBConnector(read_only=True)
            budget.check()
            # Save User Query
            if request.persist_history:
                db.save_message("default", "user", request.query)
            # Save AI Answer
            if request.persist_history:
                db.save_message("default", "ai", answer)
            db.close() # Close connection
        except ExecutionFailure:
            raise
        except Exception as e:
            print(f"⚠️ Failed to save history: {e}")
        
        latency = time.time() - start_time
        
        # Extract trace from messages (identifying tool calls/outputs)
        # LangGraph messages usually have 'type' or are BaseMessage objects
        # We need to serialize them safely
        trace = []
        if "messages" in final_state:
            for m in final_state["messages"]:
                # Persisted history uses dictionaries; graph integrations may
                # return message objects. Preserve both without assuming attrs.
                if isinstance(m, dict):
                    msg_dict = {"type": m.get("type", m.get("role", "unknown")),
                                "content": str(m.get("content", ""))}
                    tool_calls = m.get("tool_calls")
                else:
                    msg_dict = {"type": getattr(m, "type", "unknown"),
                                "content": str(getattr(m, "content", ""))}
                    tool_calls = getattr(m, "tool_calls", None)
                if tool_calls:
                    msg_dict["tool_calls"] = tool_calls
                trace.append(msg_dict)
        
        budget.check()
        return QueryResponse(
            answer=answer,
            sql=final_state.get("sql_query"),
            sql_result=final_state.get("sql_result"),
            sql_rows=final_state.get("sql_rows"),
            context=(final_state.get("web_results") if final_state.get("intent") == "web_search"
                     else final_state.get("rag_context")),
            intent=final_state.get("intent", "unknown"),
            trace=trace,
            metadata={
                "rewritten_query": final_state.get("rewritten_query"),
                "latency": latency,
                "context_feedback": final_state.get("context_feedback"),
                "answer_feedback": final_state.get("answer_feedback"),
                "outcome": final_state.get("outcome"),
                "retry_counts": {kind: final_state.get(f"{kind}_retry_count", 0)
                                 for kind in ("sql", "context", "answer")},
                "provider_calls": dict(budget.calls),
                "provenance": budget.provenance
            }
        )
    except ExecutionFailure:
        raise
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

@app.get("/alerts")
def get_alerts():
    """
    Retrieves unread alerts.
    """
    try:
        from shared.db.duckdb_client import DuckDBConnector
        # Alerts live in history.duckdb, so logs read-only is fine
        db = DuckDBConnector(read_only=True) 
        alerts = db.get_alerts()
        db.close()
        return alerts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/alerts/{alert_id}/read")
def read_alert(alert_id: str):
    """
    Marks an alert as read.
    """
    try:
        from shared.db.duckdb_client import DuckDBConnector
        # Alerts live in history.duckdb, so logs read-only is fine
        db = DuckDBConnector(read_only=True)
        db.mark_alert_read(alert_id)
        db.close()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
def get_metrics():
    from shared.evaluation import EvaluationStore
    return EvaluationStore(os.getenv("METRICS_DB_PATH", "data/target/metrics.duckdb")).summary()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
