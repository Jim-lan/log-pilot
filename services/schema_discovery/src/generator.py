import sys
import os
from typing import List

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shared.llm.client import LLMClient
from shared.llm.prompt_factory import PromptFactory

class RegexGenerator:
    """
    Uses an LLM to generate a Python regex pattern for a given set of log samples.
    """
    def __init__(self):
        self.llm = LLMClient()
        self.prompts = PromptFactory()

    def generate_regex(self, samples: List[str]) -> str:
        """
        Asks the LLM to generate a regex.
        """
        samples_str = "\n".join(samples)
        
        prompt = self.prompts.create_prompt(
            "schema_discovery",
            "regex_generator",
            samples_str=samples_str
        )
        
        # Generate regex using the prompt template
        regex_pattern = self.llm.generate(prompt, model_type="fast")
        return regex_pattern.strip()
