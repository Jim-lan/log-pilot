import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

# Mock dependencies BEFORE importing api
sys.modules["services.pilot_orchestrator.src.graph"] = MagicMock()
sys.modules["services.pilot_orchestrator.src.nodes"] = MagicMock()

from services.pilot_orchestrator.src.api import app

client = TestClient(app)

@patch("services.pilot_orchestrator.src.api.pilot_graph")
def test_run_query_returns_sql_result(mock_graph):
    # Setup Mock Graph Response
    mock_graph.invoke.return_value = {
        "final_answer": "There are 5 errors.",
        "sql_query": "SELECT count(*) FROM logs",
        "sql_result": "[('5',)]", # This is what we want to verify!
        "intent": "sql"
    }
    
    # Setup Mock DB History
    # We mocked 'services.pilot_orchestrator.src.nodes' at the top
    nodes_mock = sys.modules["services.pilot_orchestrator.src.nodes"]
    nodes_mock.sql_tool.db.get_history.return_value = []
    
    # Execute Request
    response = client.post("/query", json={"query": "count errors"})
    
    # Verify Response
    assert response.status_code == 200
    data = response.json()
    
    assert data["answer"] == "There are 5 errors."
    assert data["sql"] == "SELECT count(*) FROM logs"
    assert data["sql_result"] == "[('5',)]" # VERIFIED
    assert data["intent"] == "sql"
