from typing import List, Optional
from .generator import RegexGenerator
from .validator import RegexValidator

class DiscoveryAgent:
    """
    Orchestrates the schema discovery process:
    1. Generate Regex (LLM)
    2. Validate Regex (Python re)
    3. Retry if invalid (max retries)
    """
    def __init__(self, max_retries: int = 3):
        self.generator = RegexGenerator()
        self.validator = RegexValidator()
        self.max_retries = max_retries

    def discover_schema(self, log_samples: List[str]) -> Optional[str]:
        """
        Attempts to discover a valid regex schema for the provided log samples.
        """
        print(f"🔍 Starting Schema Discovery for {len(log_samples)} samples...")
        
        for attempt in range(1, self.max_retries + 1):
            print(f"  Attempt {attempt}/{self.max_retries}: Generating Regex...")
            regex = self.generator.generate_regex(log_samples)
            print(f"  Generated: {regex}")
            
            if self.validator.validate(regex, log_samples):
                print("✅ Schema Validated!")
                return regex
            else:
                print("❌ Validation Failed. Retrying...")
        
        print("⚠️ Failed to discover a valid schema after max retries.")
        return None
