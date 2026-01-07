from typing import Dict, Optional, Literal
from pydantic import BaseModel
import os

class ModelConfig(BaseModel):
    model_id: str
    provider: Literal["ollama", "openai", "anthropic"]
    model_name: str  # The actual name used by the provider (e.g., "llama3", "gpt-4o")
    api_base: Optional[str] = None
    api_key_env: Optional[str] = None
    temperature: float = 0.0
    top_p: float = 1.0

import yaml

class ModelRegistry:
    def __init__(self):
        self._models: Dict[str, ModelConfig] = {}
        self._load_defaults()

    def _load_config(self) -> Dict:
        # Try to load from config/llm_config.yaml
        # Path relative to this file: ../../../config/llm_config.yaml
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        config_path = os.path.join(base_path, "config/llm_config.yaml")
        
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        return {}

    def _load_defaults(self):
        config = self._load_config()
        llm_config = config.get("llm", {})
        
        # Determine default provider and model
        provider_name = llm_config.get("default_provider", "local")
        provider_config = llm_config.get("providers", {}).get(provider_name, {})
        
        # Common settings
        api_base = provider_config.get("api_base")
        if not api_base and provider_name == "local":
             api_base = os.getenv("LLM_BASE_URL", "http://log-pilot-llm:11434/v1")
        
        api_key_env = provider_config.get("api_key_env")
        
        # Map provider names
        registry_provider = "ollama" if provider_name == "local" else provider_name
        
        # Get specific models map
        models_map = provider_config.get("models", {})
        
        # Determine 'fast' model
        fast_model = models_map.get("fast")
        if not fast_model:
            fast_model = provider_config.get("default_model", os.getenv("LLM_MODEL", "llama3"))
            
        # Determine 'smart' model (map 'reasoning' -> 'smart')
        smart_model = models_map.get("reasoning")
        if not smart_model:
            smart_model = provider_config.get("default_model", os.getenv("LLM_MODEL", "llama3"))

        self.register(ModelConfig(
            model_id="fast",
            provider=registry_provider,
            model_name=fast_model,
            api_base=api_base,
            api_key_env=api_key_env,
            temperature=0.1
        ))
        
        self.register(ModelConfig(
            model_id="smart",
            provider=registry_provider,
            model_name=smart_model,
            api_base=api_base,
            api_key_env=api_key_env,
            temperature=0.1
        ))

    def register(self, config: ModelConfig):
        self._models[config.model_id] = config

    def get(self, model_id: str) -> ModelConfig:
        if model_id not in self._models:
            raise ValueError(f"Model '{model_id}' not found in registry.")
        return self._models[model_id]

# Singleton instance
registry = ModelRegistry()
