import pytest
from unittest.mock import MagicMock, patch
from services.pilot_orchestrator.src.nodes import execute_sql, retrieve_context, get_db_client, get_kb_store

@patch("services.pilot_orchestrator.src.nodes.DuckDBConnector")
def test_execute_sql_success(mock_db_connector_cls):
    # Setup Mock
    mock_db_instance = MagicMock()
    mock_db_connector_cls.return_value = mock_db_instance
    mock_db_instance.query.return_value = [(10,)] # Mock result: count=10
    
    # Reset singleton if it was already initialized
    import services.pilot_orchestrator.src.nodes as nodes
    nodes._db_client = None
    
    # Input State
    state = {"sql_query": "SELECT COUNT(*) FROM logs", "retry_count": 0}
    
    # Execute
    new_state = execute_sql(state)
    
    # Verify
    assert new_state["sql_result"] == "[(10,)]"
    assert new_state.get("sql_error") is None
    mock_db_instance.query.assert_called_with("SELECT COUNT(*) FROM logs")

@patch("services.pilot_orchestrator.src.nodes.KnowledgeStore")
def test_retrieve_context_success(mock_kb_store_cls):
    # Setup Mock
    mock_kb_instance = MagicMock()
    mock_kb_store_cls.return_value = mock_kb_instance
    mock_kb_instance.query.return_value = "Fix: Restart pod."
    
    # Reset singleton
    import services.pilot_orchestrator.src.nodes as nodes
    nodes._kb_store = None
    
    # Input State
    state = {"query": "How to fix auth error?"}
    
    # Execute
    new_state = retrieve_context(state)
    
    # Verify
    assert new_state["rag_context"] == "Fix: Restart pod."
    mock_kb_instance.query.assert_called_with("How to fix auth error?")
