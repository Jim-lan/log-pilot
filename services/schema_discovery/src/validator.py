import re
from typing import List

class RegexValidator:
    """
    Validates that a regex pattern correctly matches a set of log samples.
    """
    
    @staticmethod
    def validate(regex: str, samples: List[str]) -> bool:
        """
        Returns True if the regex matches ALL samples.
        """
        try:
            pattern = re.compile(regex)
        except re.error:
            print(f"❌ Invalid Regex Syntax: {regex}")
            return False
            
        for sample in samples:
            match = pattern.match(sample)
            if not match:
                print(f"❌ Regex failed to match sample: {sample}")
                return False
            
            # Optional: Check for named groups
            if not match.groupdict():
                print(f"⚠️ Regex matched but captured no named groups: {sample}")
                # We might want to enforce capturing groups, but for now let's just warn
                
        return True
