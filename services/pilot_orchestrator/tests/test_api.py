import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from services.pilot_orchestrator.src.api import app

# Mock the graph invocation
@patch("services.pilot_orchestrator.src.api.pilot_graph")
def test_api_query_success(mock_graph):
    client = TestClient(app)
    
    # Mock return value
    mock_graph.invoke.return_value = {
        "final_answer": "Found 5 errors.",
        "sql_query": "SELECT count(*) FROM logs",
        "rag_context": "None",
        "intent": "sql"
    }
    
    response = client.post("/query", json={"query": "count errors"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Found 5 errors."
    assert data["sql"] == "SELECT count(*) FROM logs"
    assert data["intent"] == "sql"

def test_api_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
