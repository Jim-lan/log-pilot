import pytest
from unittest.mock import MagicMock, patch
from services.pilot_orchestrator.src.nodes import classify_intent

@patch("services.pilot_orchestrator.src.nodes.llm_client")
@patch("services.pilot_orchestrator.src.nodes.prompt_factory")
def test_classify_intent_sql(mock_factory, mock_llm):
    # Setup Mocks
    mock_factory.create_prompt.return_value = "Mock Prompt"
    mock_llm.generate.return_value = "sql"
    
    # Input State
    state = {"query": "Count errors"}
    
    # Execute
    new_state = classify_intent(state)
    
    # Verify
    assert new_state["intent"] == "sql"
    mock_factory.create_prompt.assert_called_with("pilot_orchestrator", "intent_classifier", query="Count errors")

@patch("services.pilot_orchestrator.src.nodes.llm_client")
@patch("services.pilot_orchestrator.src.nodes.prompt_factory")
def test_classify_intent_rag(mock_factory, mock_llm):
    # Setup Mocks
    mock_factory.create_prompt.return_value = "Mock Prompt"
    mock_llm.generate.return_value = "rag"
    
    # Input State
    state = {"query": "How to fix?"}
    
    # Execute
    new_state = classify_intent(state)
    
    # Verify
    assert new_state["intent"] == "rag"

@patch("services.pilot_orchestrator.src.nodes.llm_client")
@patch("services.pilot_orchestrator.src.nodes.prompt_factory")
def test_classify_intent_fallback(mock_factory, mock_llm):
    # Setup Mocks
    mock_factory.create_prompt.return_value = "Mock Prompt"
    mock_llm.generate.return_value = "unknown_intent"
    
    # Input State
    state = {"query": "blah"}
    
    # Execute
    new_state = classify_intent(state)
    
    # Verify fallback to ambiguous
    assert new_state["intent"] == "ambiguous"
