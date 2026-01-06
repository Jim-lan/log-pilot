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

class ModelRegistry:
    def __init__(self):
        self._models: Dict[str, ModelConfig] = {}
        self._load_defaults()

    def _load_defaults(self):
        # Default Local Models
        self.register(ModelConfig(
            model_id="fast",
            provider="ollama",
            model_name=os.getenv("LLM_MODEL", "llama3"),
            api_base=os.getenv("LLM_BASE_URL", "http://log-pilot-llm:11434/v1"),
            temperature=0.1
        ))
        
        self.register(ModelConfig(
            model_id="smart",
            provider="ollama",
            model_name=os.getenv("LLM_MODEL", "llama3"), # Using same for now, but could be different
            api_base=os.getenv("LLM_BASE_URL", "http://log-pilot-llm:11434/v1"),
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
