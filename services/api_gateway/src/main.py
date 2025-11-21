import sys
import os
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from services.api_gateway.src.models import QueryRequest, QueryResponse
from services.pilot_orchestrator.src.graph import pilot_graph

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic if needed
    print("🚀 API Gateway Starting...")
    yield
    # Shutdown logic if needed
    print("🛑 API Gateway Stopping...")

app = FastAPI(title="LogPilot API", version="2.0.0", lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api-gateway"}

@app.post("/query", response_model=QueryResponse)
async def query_agent(request: QueryRequest):
    """
    Submit a natural language query to the LogPilot Agent.
    """
    try:
        # Initialize state
        initial_state = {
            "query": request.query,
            "retry_count": 0,
            "history": []
        }
        
        # Invoke LangGraph
        # Note: invoke is synchronous. For high throughput, we'd use ainvoke or run in a threadpool.
        result = pilot_graph.invoke(initial_state)
        
        response_context = {}
        if result.get("intent") == "sql":
            response_context["sql"] = result.get("sql_query")
            response_context["sql_result"] = result.get("sql_result")
        elif result.get("intent") == "rag":
            response_context["rag_context"] = result.get("rag_context")

        return QueryResponse(
            answer=result.get("final_answer"),
            intent=result.get("intent"),
            context=response_context,
            error=result.get("sql_error") # Return SQL error if present even if answer was synthesized
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
