import os
import yaml
from typing import Optional, Dict, Any
import openai
from shared.execution import invoke_provider, ExecutionFailure, setting

# Try to import ModelRegistry
try:
    from services.pilot_orchestrator.src.model_registry import registry
except ImportError:
    registry = None

# Try to import TokenCounter
try:
    from services.pilot_orchestrator.src.token_counter import token_counter
except ImportError:
    token_counter = None

class LLMClient:
    """
    A unified client for interacting with LLM providers.
    Uses Model Registry for configuration.
    """
    def __init__(self, config_path: str = "config/llm_config.yaml"):
        # Load file-based config (used if ModelRegistry is unavailable)
        self.config = self._load_config(config_path)
        self._clients = {} # Cache clients by base_url
        self.max_input_tokens = 4096 # Safety limit

    def _load_config(self, path: str) -> Dict[str, Any]:
        # Resolve absolute path relative to project root
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        full_path = os.path.join(base_path, path)
        
        if not os.path.exists(full_path):
            # Fallback for tests or if file missing
            return {"llm": {"default_provider": "local", "providers": {"local": {"api_base": "http://localhost:11434"}}}}
            
        with open(full_path, "r") as f:
            return yaml.safe_load(f)

    def _get_client(self, api_base: str, api_key: str) -> openai.OpenAI:
        cache_key = f"{api_base}:{api_key}"
        if cache_key not in self._clients:
            self._clients[cache_key] = openai.OpenAI(
                api_key=api_key,
                base_url=api_base,
                timeout=setting("LOGPILOT_LLM_TIMEOUT_SECONDS", 30),
                max_retries=0
            )
        return self._clients[cache_key]

    def generate(self, prompt: str, model_type: str = "fast") -> str:
        """
        Generates text from the LLM using the Model Registry.
        """
        if registry:
            try:
                config = registry.get(model_type)
                model_name = config.model_name
                api_base = config.api_base
                api_key = os.getenv(config.api_key_env, "dummy") if config.api_key_env else "dummy"
                temperature = config.temperature
            except ValueError:
                # Fallback to legacy config if model_id not in registry
                return self._generate_legacy(prompt, model_type)
        else:
            return self._generate_legacy(prompt, model_type)

        return self._complete(prompt, model_name, api_base, api_key, temperature)

    def _complete(self, prompt, model_name, api_base, api_key, temperature):
        from shared.privacy import redact_outbound
        prompt = redact_outbound(prompt)
        from shared.execution import current_budget
        budget = current_budget()
        call = {'requested_model': model_name, 'returned_model': None,
                'temperature': temperature, 'system_fingerprint': None, 'outcome': 'started'}
        if budget is not None:
            with budget.lock:
                budget.provenance['model_calls'].append(call)

        def update(**fields):
            if budget is not None:
                with budget.lock:
                    call.update(fields)
            else:
                call.update(fields)

        def request(timeout):
            if token_counter and token_counter.count_tokens(prompt, model_name) > self.max_input_tokens:
                raise ExecutionFailure()
            client = self._get_client(api_base, api_key).with_options(timeout=timeout, max_retries=0)
            response = client.chat.completions.create(
                model=model_name, messages=[{"role": "user", "content": prompt}], temperature=temperature)
            update(returned_model=response.model, system_fingerprint=response.system_fingerprint)
            content = response.choices[0].message.content
            if not isinstance(content, str) or not content.strip():
                raise ExecutionFailure()
            return content
        try:
            result = invoke_provider('llm', request)
        except BaseException:
            update(outcome='failed')
            raise
        update(outcome='completed')
        return result

    def _generate_legacy(self, prompt: str, model_type: str) -> str:
        # ... (Previous implementation for backward compatibility)
        # For brevity, reusing the logic from original file but simplified
        provider_name = self.config["llm"]["default_provider"]
        provider_config = self.config["llm"]["providers"][provider_name]
        api_base = provider_config.get("api_base")
        api_key = os.getenv(provider_config.get("api_key_env", ""), "dummy")
        
        models_config = provider_config.get("models", {})
        model_name = models_config.get(model_type, provider_config.get("default_model", "gpt-3.5-turbo"))
        
        return self._complete(prompt, model_name, api_base, api_key, 0.2)

    def check_health(self) -> Dict[str, Any]:
        """
        Checks if the LLM provider is ready.
        """
        # Simple health check using 'fast' model from registry
        try:
            if registry:
                config = registry.get("fast")
                client = self._get_client(config.api_base, "dummy")
                invoke_provider("health", lambda timeout: client.with_options(timeout=timeout, max_retries=0).models.list())
                return {"status": "ready", "model": config.model_name}
            else:
                return {"status": "unknown", "details": "Registry not loaded"}
        except Exception as e:
            return {"status": "error", "details": str(e)}
