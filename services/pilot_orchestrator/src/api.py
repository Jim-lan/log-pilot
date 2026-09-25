import sys
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
from shared.execution import RequestBudget, ExecutionFailure, DeadlineExceeded, use_budget, setting
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, model_validator
from shared.evaluation_context import EvaluationContext
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
    evaluation_context: Optional[EvaluationContext] = None

    @model_validator(mode='after')
    def separate_evaluation_history(self):
        if self.evaluation_context is not None and self.persist_history:
            raise ValueError('Evaluation context requires persist_history=false')
        return self

class QueryResponse(BaseModel):
    answer: str
    sql: Optional[str] = None
    sql_result: Optional[str] = None
    sql_rows: Optional[List[List[Any]]] = None
    context: Optional[str] = None
    sources: List[Dict[str, Any]] = []
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
    def failure_response(status, code, message):
        budget.trace.finish(budget.trace.root, 'failed', code)
        return HTTPException(status_code=status, detail={
            'code': code, 'message': message, **budget.trace.metadata(), 'trace': budget.trace.snapshot(),
            'provenance': budget.provenance_snapshot()})

    if not query_slots.acquire(blocking=False):
        raise failure_response(503, 'query_capacity_exhausted', 'All query workers are busy. Please retry later.')

    def work():
        try:
            with use_budget(budget):
                return _run_query(request, budget)
        finally:
            query_slots.release()

    try:
        future = asyncio.get_running_loop().run_in_executor(query_executor, work)
    except Exception:
        query_slots.release()
        raise failure_response(500, 'internal_error', 'The query could not complete.') from None
    future.add_done_callback(lambda completed: completed.exception() if not completed.cancelled() else None)
    try:
        response = await asyncio.wait_for(asyncio.shield(future), timeout=budget.remaining())
        outcome = response.metadata.get('outcome')
        if outcome in ('insufficient_evidence', 'abstained'):
            budget.trace.finish(budget.trace.root, 'abstained', 'insufficient_evidence')
        elif outcome == 'dependency_error':
            budget.trace.finish(budget.trace.root, 'failed', 'dependency_error')
        else:
            budget.trace.finish(budget.trace.root)
        response.trace = budget.trace.snapshot()
        response.metadata.update(budget.trace.metadata())
        return response
    except asyncio.TimeoutError:
        budget.cancel()
        failure = DeadlineExceeded()
        raise failure_response(failure.status, failure.code, failure.message) from None
    except ExecutionFailure as failure:
        raise failure_response(failure.status, failure.code, failure.message) from None
    except Exception:
        raise failure_response(500, 'internal_error', 'The query could not complete.') from None


def _run_query(request: QueryRequest, budget: RequestBudget):
    """
    Executes the Pilot Agent for a given query.
    """
    try:
        import time
        start_time = time.time()
        budget.check()
        from shared.db.duckdb_client import DuckDBConnector
        messages = request.evaluation_context.model_dump() if request.evaluation_context is not None else []
        if request.persist_history:
            db = DuckDBConnector(read_only=True)
            try:
                history_rows = db.get_history("default")
                messages = [{"role": row[0], "content": row[1]} for row in history_rows[-10:]]
            finally:
                db.close()

        # Initialize state with history
        initial_state = {"query": request.query, "messages": messages}
        
        # Run the graph
        # invoke returns the final state
        final_state = pilot_graph.invoke(initial_state)
        budget.check()
        
        answer = final_state.get("final_answer", "No answer generated.")
        
        # Save to History (Session ID = default for demo)
        try:
            budget.check()
            if request.persist_history:
                db = DuckDBConnector(read_only=True)
                try:
                    db.save_message("default", "user", request.query)
                    db.save_message("default", "ai", answer)
                finally:
                    db.close()
        except ExecutionFailure:
            raise
        except Exception as e:
            print(f"⚠️ Failed to save history: {e}")
        
        latency = time.time() - start_time
        
        budget.check()
        return QueryResponse(
            answer=answer,
            sql=final_state.get("sql_query"),
            sql_result=final_state.get("sql_result"),
            sql_rows=final_state.get("sql_rows"),
            context=(final_state.get("web_results") if final_state.get("intent") == "web_search"
                     else final_state.get("rag_context")),
            intent=final_state.get("intent", "unknown"),
            trace=[],
            sources=final_state.get("sources", []),
            metadata={
                "rewritten_query": final_state.get("rewritten_query"),
                "latency": latency,
                "context_feedback": final_state.get("context_feedback"),
                "answer_feedback": final_state.get("answer_feedback"),
                "outcome": final_state.get("outcome"),
                "retry_counts": {kind: final_state.get(f"{kind}_retry_count", 0)
                                 for kind in ("sql", "context", "answer")},
                "provider_calls": dict(budget.calls),
                "provenance": budget.provenance_snapshot()
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
