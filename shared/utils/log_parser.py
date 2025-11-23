import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any

class LogParser:
    """
    Robust log parser using Regex and enforcing UTC timestamps.
    """
    # Default pattern: Timestamp Level Service Body
    # Example: 2025-11-20 10:00:01 INFO payment-service: Payment processed...
    LOG_PATTERN = re.compile(
        r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+'  # YYYY-MM-DD HH:MM:SS
        r'(?P<severity>\w+)\s+'                                   # INFO, ERROR
        r'(?P<service>[\w-]+)(?::)?\s+'                           # service-name (optional colon)
        r'(?P<message>.*)',                                       # Rest of the line
        re.DOTALL                                                 # Allow matching across newlines
    )

    def parse(self, raw_log: str) -> Dict[str, Any]:
        """
        Parses a raw log string into structured components.
        """
        match = self.LOG_PATTERN.match(raw_log.strip())
        if not match:
            # Fallback for non-matching logs (e.g. stack traces if not aggregated)
            # For now, we treat them as "UNKNOWN" or raise error
            # In a real stream, we might buffer these.
            raise ValueError("Log format not recognized")

        data = match.groupdict()
        
        # Normalize Timestamp to UTC
        # Assuming input is local time if no timezone info, we set it to UTC for standardization
        dt = datetime.strptime(data["timestamp"], "%Y-%m-%d %H:%M:%S")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        return {
            "timestamp": dt,
            "severity": data["severity"],
            "service_name": data["service"],
            "body": data["message"]
        }
