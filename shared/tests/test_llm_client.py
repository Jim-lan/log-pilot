import pytest
from unittest.mock import MagicMock, patch
from shared.llm.client import LLMClient

@patch("shared.llm.client.openai.OpenAI")
def test_llm_client_init_openai(mock_openai):
    # Setup Mock Config
    mock_config = {
        "llm": {
            "default_provider": "openai",
            "providers": {
                "openai": {
                    "api_key_env": "OPENAI_API_KEY",
                    "models": {"fast": "gpt-4o-mini"}
                }
            }
        }
    }
    
    with patch("shared.llm.client.yaml.safe_load", return_value=mock_config):
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", MagicMock()):
                with patch("os.getenv", return_value="sk-test-key"):
                    client = LLMClient()
                    
                    # Verify OpenAI init
                    mock_openai.assert_called_with(api_key="sk-test-key", base_url=None)

@patch("shared.llm.client.openai.OpenAI")
def test_llm_client_init_local(mock_openai):
    # Setup Mock Config for Local
    mock_config = {
        "llm": {
            "default_provider": "local",
            "providers": {
                "local": {
                    "api_base": "http://localhost:11434/v1",
                    "default_model": "llama3"
                }
            }
        }
    }
    
    with patch("shared.llm.client.yaml.safe_load", return_value=mock_config):
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", MagicMock()):
                client = LLMClient()
                
                # Verify OpenAI init with base_url
                mock_openai.assert_called_with(api_key="dummy", base_url="http://localhost:11434/v1")

@patch("shared.llm.client.openai.OpenAI")
def test_generate(mock_openai):
    # Setup Mock Client
    mock_client_instance = MagicMock()
    mock_openai.return_value = mock_client_instance
    
    # Mock Response
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Hello World"
    mock_client_instance.chat.completions.create.return_value = mock_response
    
    # Setup Config
    mock_config = {
        "llm": {
            "default_provider": "openai",
            "providers": {
                "openai": {
                    "api_key_env": "OPENAI_API_KEY",
                    "models": {"fast": "gpt-4o-mini"}
                }
            }
        }
    }
    
    with patch("shared.llm.client.yaml.safe_load", return_value=mock_config):
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", MagicMock()):
                with patch("os.getenv", return_value="sk-test"):
                    client = LLMClient()
                    response = client.generate("Hi", model_type="fast")
                    
                    assert response == "Hello World"
                    mock_client_instance.chat.completions.create.assert_called()
