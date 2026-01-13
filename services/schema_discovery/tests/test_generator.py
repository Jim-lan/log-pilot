import pytest
from unittest.mock import MagicMock, patch
from services.schema_discovery.src.generator import RegexGenerator

@patch("services.schema_discovery.src.generator.LLMClient")
@patch("services.schema_discovery.src.generator.PromptFactory")
def test_generate_regex_uses_template(mock_factory_cls, mock_llm_cls):
    # Setup Mocks
    mock_llm = mock_llm_cls.return_value
    mock_factory = mock_factory_cls.return_value
    
    mock_llm.generate.return_value = r"(?P<test>\d+)"
    mock_factory.create_prompt.return_value = "Mock Prompt"
    
    # Run
    generator = RegexGenerator()
    samples = ["line1", "line2"]
    result = generator.generate_regex(samples)
    
    # Verify
    assert result == r"(?P<test>\d+)"
    
    # Check that create_prompt was called with correct arguments
    mock_factory.create_prompt.assert_called_once_with(
        "schema_discovery",
        "regex_generator",
        samples_str="line1\nline2"
    )
    
    # Check that LLM generate was called with the rendered prompt
    mock_llm.generate.assert_called_once_with("Mock Prompt", model_type="fast")
