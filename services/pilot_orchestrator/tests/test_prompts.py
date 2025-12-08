import pytest
from shared.llm.prompt_factory import PromptFactory

def test_sql_generator_template():
    factory = PromptFactory()
    prompt = factory.create_prompt(
        "pilot_orchestrator", 
        "sql_generator", 
        query="Count errors"
    )
    
    assert "DuckDB SQL query" in prompt
    assert "logs" in prompt
    assert "Count errors" in prompt

def test_synthesize_answer_template():
    factory = PromptFactory()
    prompt = factory.create_prompt(
        "pilot_orchestrator", 
        "synthesize_answer", 
        query="What happened?",
        context="Found 5 errors."
    )
    
    assert "LogPilot" in prompt
    assert "What happened?" in prompt
    assert "Found 5 errors." in prompt
