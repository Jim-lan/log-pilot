import re
from typing import Any, Dict, Union

class PIIMasker:
    """
    Utility class to mask Personally Identifiable Information (PII) 
    from log messages and context dictionaries.
    """
    
    # Pre-compiled regex patterns for common PII
    PATTERNS = {
        "email": (r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '<EMAIL_REDACTED>'),
        "ipv4": (r'(?<!\d)(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(?!\d)', '<IP_REDACTED>'),
        "credit_card": (r'\b(?:\d[ -]*?){13,16}\b', '<CC_REDACTED>'),
        "ssn": (r'\b\d{3}-\d{2}-\d{4}\b', '<SSN_REDACTED>'),
    }

    def __init__(self):
        self.regexes = {k: (re.compile(p), r) for k, (p, r) in self.PATTERNS.items()}

    def mask_text(self, text: str) -> str:
        """Masks PII in a string."""
        if not text:
            return text
            
        masked_text = text
        for name, (pattern, replacement) in self.regexes.items():
            masked_text = pattern.sub(replacement, masked_text)
        return masked_text

    def mask_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively masks PII in a dictionary."""
        masked_context = {}
        for k, v in context.items():
            if isinstance(v, str):
                masked_context[k] = self.mask_text(v)
            elif isinstance(v, dict):
                masked_context[k] = self.mask_context(v)
            elif isinstance(v, list):
                masked_context[k] = [
                    self.mask_text(i) if isinstance(i, str) else i 
                    for i in v
                ]
            else:
                masked_context[k] = v
        return masked_context
