import os
import yaml
from typing import Optional, Dict, Any
import openai

class LLMClient:
    """
    A unified client for interacting with LLM providers (OpenAI, Gemini, Local).
    Reads configuration from config/llm_config.yaml.
    """
    def __init__(self, config_path: str = "config/llm_config.yaml"):
        self.config = self._load_config(config_path)
        self.provider_name = self.config["llm"]["default_provider"]
        self.provider_config = self.config["llm"]["providers"][self.provider_name]
        
        self.api_key = self._get_api_key()
        self.base_url = self.provider_config.get("api_base")
        
        # Initialize OpenAI Client
        # This works for OpenAI, Gemini (via adapter), and Local (Ollama/vLLM)
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def _load_config(self, path: str) -> Dict[str, Any]:
        # Resolve absolute path relative to project root
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        full_path = os.path.join(base_path, path)
        
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Config file not found at {full_path}")
            
        with open(full_path, "r") as f:
            return yaml.safe_load(f)

    def _get_api_key(self) -> str:
        env_var = self.provider_config.get("api_key_env")
        if not env_var:
            return "dummy" # For local providers that don't need key
            
        api_key = os.getenv(env_var)
        if not api_key:
             if self.provider_name == "local":
                 return "dummy"
             print(f"⚠️  WARNING: {env_var} not set. LLM calls will fail.")
             return "missing"
        return api_key

    def generate(self, prompt: str, model_type: str = "fast") -> str:
        """
        Generates text from the LLM.
        """
        # Get model name from config
        # Handle both 'models' dict (cloud) and 'default_model' (local)
        models_config = self.provider_config.get("models", {})
        model_name = models_config.get(model_type)
        
        if not model_name:
             model_name = self.provider_config.get("default_model", "gpt-3.5-turbo")

        print(f"🤖 LLM Call ({self.provider_name}/{model_name}): {prompt[:50]}...")
        
        try:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"❌ Error generating response: {e}"
            return f"❌ Error generating response: {e}"

    def check_health(self) -> Dict[str, Any]:
        """
        Checks if the LLM provider is ready and the model is available.
        """
        try:
            # For local provider, check if model is loaded/available
            if self.provider_name == "local":
                model_name = self.provider_config.get("default_model", "llama3")
                try:
                    models = self.client.models.list()
                    # OpenAI client returns objects with .id attribute
                    available_models = [m.id for m in models.data]
                    
                    # Ollama might return 'llama3:latest', so check partial match
                    is_ready = any(model_name in m for m in available_models)
                    
                    if is_ready:
                        return {"status": "ready", "model": model_name}
                    else:
                        return {"status": "downloading", "model": model_name, "details": "Model not found in list"}
                except Exception as e:
                    return {"status": "error", "details": f"Failed to list models: {str(e)}"}
            
            # For cloud providers, assume ready if client initialized
            return {"status": "ready", "model": self.provider_name}
            
        except Exception as e:
            return {"status": "error", "details": str(e)}
