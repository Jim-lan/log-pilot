import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from services.api_gateway.src.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "api-gateway"}

@patch("services.api_gateway.src.main.pilot_graph")
def test_query_endpoint(mock_graph):
    # Mock the graph response
    mock_graph.invoke.return_value = {
        "intent": "sql",
        "final_answer": "There are 5 errors.",
        "sql_query": "SELECT count(*) FROM logs",
        "sql_result": "5"
    }
    
    payload = {"query": "How many errors?"}
    response = client.post("/query", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "There are 5 errors."
    assert data["intent"] == "sql"
    assert data["context"]["sql"] == "SELECT count(*) FROM logs"

@patch("services.api_gateway.src.main.pilot_graph")
def test_query_endpoint_error(mock_graph):
    # Mock an exception
    mock_graph.invoke.side_effect = Exception("Graph failed")
    
    payload = {"query": "Crash me"}
    response = client.post("/query", json=payload)
    
    assert response.status_code == 500
    assert "Graph failed" in response.json()["detail"]
