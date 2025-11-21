import sys
import os
from typing import List

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shared.llm.client import LLMClient

class RegexGenerator:
    """
    Uses an LLM to generate a Python regex pattern for a given set of log samples.
    """
    def __init__(self):
        self.llm = LLMClient()

    def generate_regex(self, samples: List[str]) -> str:
        """
        Asks the LLM to generate a regex.
        """
        samples_str = "\n".join(samples)
        prompt = f"""
You are an expert in Regular Expressions (Regex) for Python.
Your task is to generate a Python regex pattern that can parse the following log lines.
The regex MUST capture the following fields if present: timestamp, severity, service, message.
Use named groups like (?P<timestamp>...), (?P<severity>...), etc.

Log Samples:
{samples_str}

Return ONLY the regex pattern, nothing else. Do not wrap in code blocks.
"""
        # In a real scenario, we'd use a more robust prompt or structured output
        regex_pattern = self.llm.generate(prompt, model_type="fast")
        return regex_pattern.strip()
