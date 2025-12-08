import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from services.pilot_orchestrator.src.api import app

client = TestClient(app)

@patch("services.pilot_orchestrator.src.nodes.llm_client")
@patch("services.pilot_orchestrator.src.nodes.prompt_factory")
@patch("services.pilot_orchestrator.src.nodes.sql_tool")
@patch("services.pilot_orchestrator.src.nodes.get_db_client")
def test_e2e_sql_flow(mock_db_getter, mock_sql_tool, mock_factory, mock_llm):
    # 1. Setup Mocks
    # Intent Classifier -> "sql"
    # SQL Generator -> "SELECT..."
    # Synthesizer -> "Final Answer"
    
    # We need to mock the LLM responses in sequence or based on prompt
    # Since the graph calls LLM multiple times, we can use side_effect
    
    def llm_side_effect(prompt, model_type="fast"):
        if "intent_classifier" in str(prompt):
            return "sql"
        if "synthesize_answer" in str(prompt):
            return "Found 100 errors."
        return "unknown"

    mock_llm.generate.side_effect = llm_side_effect
    
    # Mock SQL Tool
    mock_sql_tool.generate_sql.return_value = "SELECT count(*) FROM logs"
    
    # Mock DB
    mock_db = MagicMock()
    mock_db.query.return_value = [(100,)]
    mock_db_getter.return_value = mock_db
    
    # Mock Prompt Factory (just return the name for checking)
    mock_factory.create_prompt.side_effect = lambda agent, task, **kwargs: f"{task}_prompt"

    # 2. Execute Request
    payload = {"query": "How many errors in auth service?"}
    response = client.post("/query", json=payload)
    
    # 3. Verify Response
    assert response.status_code == 200
    data = response.json()
    
    print(f"E2E Response: {data}")
    
    assert data["intent"] == "sql"
    assert data["sql"] == "SELECT count(*) FROM logs"
    assert data["answer"] == "Found 100 errors."
    
    # Verify DB was called
    mock_db.query.assert_called_once()

@patch("services.pilot_orchestrator.src.nodes.llm_client")
@patch("services.pilot_orchestrator.src.nodes.prompt_factory")
@patch("services.pilot_orchestrator.src.nodes.get_kb_store")
def test_e2e_rag_flow(mock_kb_getter, mock_factory, mock_llm):
    # 1. Setup Mocks
    def llm_side_effect(prompt, model_type="fast"):
        if "intent_classifier" in str(prompt):
            return "rag"
        if "synthesize_answer" in str(prompt):
            return "Restart the pod."
        return "unknown"

    mock_llm.generate.side_effect = llm_side_effect
    
    # Mock KB
    mock_kb = MagicMock()
    mock_kb.query.return_value = "Runbook: Restart pod."
    mock_kb_getter.return_value = mock_kb
    
    mock_factory.create_prompt.side_effect = lambda agent, task, **kwargs: f"{task}_prompt"

    # 2. Execute Request
    payload = {"query": "How to fix 503 error?"}
    response = client.post("/query", json=payload)
    
    # 3. Verify Response
    assert response.status_code == 200
    data = response.json()
    
    assert data["intent"] == "rag"
    assert data["context"] == "Runbook: Restart pod."
    assert data["answer"] == "Restart the pod."
