from typing import List, Optional
from .generator import RegexGenerator
from .validator import RegexValidator

class DiscoveryAgent:
    """
    Orchestrates the schema discovery process using an Agentic Feedback Loop:
    
    1. Generate: LLM proposes a regex pattern based on log samples.
    2. Validate: Deterministic check (Python `re` module) against all samples to ensure High Recall.
    3. Refine: If validation fails, the loop continues (Retries).
       (Future improvement: Pass validation error back to LLM for smarter refinement)
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
