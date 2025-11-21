import os
import yaml
from typing import Optional, Dict, Any

class LLMClient:
    """
    A unified client for interacting with LLM providers (OpenAI, Gemini).
    Reads configuration from config/llm_config.yaml.
    """
    def __init__(self, config_path: str = "config/llm_config.yaml"):
        self.config = self._load_config(config_path)
        self.provider_name = self.config["llm"]["default_provider"]
        self.provider_config = self.config["llm"]["providers"][self.provider_name]
        self._validate_api_key()

    def _load_config(self, path: str) -> Dict[str, Any]:
        # Resolve absolute path relative to project root
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        full_path = os.path.join(base_path, path)
        
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Config file not found at {full_path}")
            
        with open(full_path, "r") as f:
            return yaml.safe_load(f)

    def _validate_api_key(self):
        env_var = self.provider_config["api_key_env"]
        if not os.getenv(env_var):
            # In production, raise error. For prototype, just warn.
            print(f"⚠️  WARNING: {env_var} not set. LLM calls will fail.")

    def generate(self, prompt: str, model_type: str = "fast", **kwargs) -> str:
        """
        Generates text using the configured provider and model type.
        model_type: 'fast' or 'reasoning'
        """
        model_name = self.provider_config["models"].get(model_type)
        if not model_name:
            raise ValueError(f"Unknown model type: {model_type}")

        # Mock Implementation for now (until we add real API calls)
        # This allows us to test the framework without paying for tokens yet.
        print(f"🤖 [LLM Mock] Provider: {self.provider_name}, Model: {model_name}")
        print(f"📝 [Prompt]: {prompt[:50]}...")
        
        if "SQL" in prompt:
            return "SELECT count(*) FROM logs"
        return "Mock LLM Response"
