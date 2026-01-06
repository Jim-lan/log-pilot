import tiktoken
from typing import Literal

class TokenCounter:
    def __init__(self):
        # Cache encodings
        self._encodings = {}

    def get_encoding(self, model_name: str):
        # Map models to encodings
        if "gpt-4" in model_name or "gpt-3.5" in model_name:
            encoding_name = "cl100k_base"
        else:
            # Default to cl100k_base for Llama 3 / others as a good approximation
            encoding_name = "cl100k_base"
            
        if encoding_name not in self._encodings:
            self._encodings[encoding_name] = tiktoken.get_encoding(encoding_name)
            
        return self._encodings[encoding_name]

    def count_tokens(self, text: str, model_name: str = "gpt-3.5-turbo") -> int:
        try:
            encoding = self.get_encoding(model_name)
            return len(encoding.encode(text))
        except Exception as e:
            print(f"⚠️ Token counting failed: {e}")
            # Fallback heuristic: ~4 chars per token
            return len(text) // 4

# Singleton
token_counter = TokenCounter()
