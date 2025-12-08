import pytest
from unittest.mock import MagicMock, patch
from services.pilot_orchestrator.src.nodes import classify_intent, generate_sql, execute_sql, synthesize_answer
from services.pilot_orchestrator.src.state import AgentState

@pytest.fixture
def mock_state():
    return {
        "query": "How many errors?",
        "intent": None,
        "sql_query": None,
        "sql_result": None,
        "sql_error": None,
        "rag_context": None,
        "final_answer": None,
        "retry_count": 0,
        "history": []
    }

@patch("services.pilot_orchestrator.src.nodes.llm_client")
@patch("services.pilot_orchestrator.src.nodes.prompt_factory")
def test_classify_intent_sql(mock_factory, mock_llm, mock_state):
    mock_state["query"] = "count errors"
    mock_llm.generate.return_value = "sql"
    new_state = classify_intent(mock_state)
    assert new_state["intent"] == "sql"

@patch("services.pilot_orchestrator.src.nodes.llm_client")
@patch("services.pilot_orchestrator.src.nodes.prompt_factory")
def test_classify_intent_rag(mock_factory, mock_llm, mock_state):
    mock_state["query"] = "why did it fail?"
    mock_llm.generate.return_value = "rag"
    new_state = classify_intent(mock_state)
    assert new_state["intent"] == "rag"

@patch("services.pilot_orchestrator.src.nodes.sql_tool")
def test_generate_sql(mock_sql_tool, mock_state):
    mock_sql_tool.generate_sql.return_value = "SELECT count(*) FROM logs"
    new_state = generate_sql(mock_state)
    assert new_state["sql_query"] == "SELECT count(*) FROM logs"
    assert new_state["sql_error"] is None

@patch("services.pilot_orchestrator.src.nodes.get_db_client")
def test_execute_sql_mock(mock_get_db, mock_state):
    # Mock DB Client
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    mock_db.query.return_value = [(10,)]
    
    mock_state["sql_query"] = "SELECT * FROM logs"
    new_state = execute_sql(mock_state)
    
    assert "[(10,)]" in new_state["sql_result"]
    mock_db.query.assert_called_with("SELECT * FROM logs")

@patch("services.pilot_orchestrator.src.nodes.llm_client")
@patch("services.pilot_orchestrator.src.nodes.prompt_factory")
def test_synthesize_answer(mock_factory, mock_llm, mock_state):
    mock_state["intent"] = "sql"
    mock_state["sql_result"] = "10 errors"
    mock_llm.generate.return_value = "There are 10 errors."
    
    new_state = synthesize_answer(mock_state)
    assert new_state["final_answer"] == "There are 10 errors."
