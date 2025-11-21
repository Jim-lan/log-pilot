import pytest
from unittest.mock import MagicMock, patch
from services.schema_discovery.src.agent import DiscoveryAgent

@patch("services.schema_discovery.src.agent.RegexGenerator")
@patch("services.schema_discovery.src.agent.RegexValidator")
def test_discover_schema_success(mock_validator_cls, mock_generator_cls):
    # Setup Mocks
    mock_generator = mock_generator_cls.return_value
    mock_validator = mock_validator_cls.return_value
    
    mock_generator.generate_regex.return_value = r"(?P<timestamp>\d+)"
    mock_validator.validate.return_value = True
    
    # Run Agent
    agent = DiscoveryAgent()
    samples = ["123456"]
    result = agent.discover_schema(samples)
    
    # Verify
    assert result == r"(?P<timestamp>\d+)"
    mock_validator.validate.assert_called_once()

@patch("services.schema_discovery.src.agent.RegexGenerator")
@patch("services.schema_discovery.src.agent.RegexValidator")
def test_discover_schema_retry_then_success(mock_validator_cls, mock_generator_cls):
    # Setup Mocks
    mock_generator = mock_generator_cls.return_value
    mock_validator = mock_validator_cls.return_value
    
    # First attempt fails, second succeeds
    mock_generator.generate_regex.side_effect = ["bad_regex", "good_regex"]
    mock_validator.validate.side_effect = [False, True]
    
    # Run Agent
    agent = DiscoveryAgent()
    samples = ["123456"]
    result = agent.discover_schema(samples)
    
    # Verify
    assert result == "good_regex"
    assert mock_generator.generate_regex.call_count == 2

@patch("services.schema_discovery.src.agent.RegexGenerator")
@patch("services.schema_discovery.src.agent.RegexValidator")
def test_discover_schema_failure(mock_validator_cls, mock_generator_cls):
    # Setup Mocks
    mock_generator = mock_generator_cls.return_value
    mock_validator = mock_validator_cls.return_value
    
    # All attempts fail
    mock_generator.generate_regex.return_value = "bad_regex"
    mock_validator.validate.return_value = False
    
    # Run Agent
    agent = DiscoveryAgent(max_retries=2)
    samples = ["123456"]
    result = agent.discover_schema(samples)
    
    # Verify
    assert result is None
    assert mock_generator.generate_regex.call_count == 2
