import re
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any

class LogParser:
    """
    Robust log parser supporting multiple formats (JSON, Syslog, Nginx, Standard).
    Enforces UTC timestamps.
    """
    
    # 1. Standard: YYYY-MM-DD HH:MM:SS LEVEL Service: Body
    PATTERN_STANDARD = re.compile(
        r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+'
        r'(?P<severity>\w+)\s+'
        r'(?P<service>[\w-]+)(?::)?\s+'
        r'(?P<message>.*)',
        re.DOTALL
    )

    # 2. Syslog: Mon DD HH:MM:SS Host Service: Body
    # Example: Nov 24 16:00:00 myhost myservice[123]: message
    PATTERN_SYSLOG = re.compile(
        r'(?P<timestamp>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+'
        r'(?P<host>[\w.-]+)\s+'
        r'(?P<service>[\w\.-]+)(?:\[\d+\])?:\s+'
        r'(?P<message>.*)',
        re.DOTALL
    )

    # 3. Nginx/Apache: IP - - [Date] "Request" Status Bytes
    # Example: 127.0.0.1 - - [24/Nov/2025:16:00:00 +0000] "GET / HTTP/1.1" 200 123
    PATTERN_NGINX = re.compile(
        r'(?P<ip>[\d.]+)\s+-\s+-\s+'
        r'\[(?P<timestamp>.*?)\]\s+'
        r'"(?P<request>.*?)"\s+'
        r'(?P<status>\d+)\s+'
        r'(?P<bytes>\d+)',
        re.DOTALL
    )

    def parse(self, raw_log: str) -> Dict[str, Any]:
        """
        Parses a raw log string into structured components.
        """
        raw_log = raw_log.strip()
        
        # Strategy 1: JSON
        if raw_log.startswith("{"):
            try:
                return self._parse_json(raw_log)
            except json.JSONDecodeError:
                pass # Not valid JSON, fall through

        # Strategy 2: Regex Patterns
        # Try Standard
        match = self.PATTERN_STANDARD.match(raw_log)
        if match:
            return self._normalize(match.groupdict(), "standard")

        # Try Syslog
        match = self.PATTERN_SYSLOG.match(raw_log)
        if match:
            return self._normalize(match.groupdict(), "syslog")
            
        # Try Nginx
        match = self.PATTERN_NGINX.match(raw_log)
        if match:
            return self._normalize(match.groupdict(), "nginx")

        # Strategy 3: Fallback
        return {
            "timestamp": datetime.now(timezone.utc),
            "severity": "UNKNOWN",
            "service_name": "unknown",
            "body": raw_log,
            "context": {"parse_error": "format_unknown"}
        }

    def _parse_json(self, raw_log: str) -> Dict[str, Any]:
        data = json.loads(raw_log)
        # Map common JSON fields to our schema
        return {
            "timestamp": self._parse_timestamp(data.get("timestamp") or data.get("time") or data.get("date")),
            "severity": data.get("severity") or data.get("level") or "INFO",
            "service_name": data.get("service") or data.get("app") or "unknown",
            "body": data.get("message") or data.get("msg") or raw_log,
            "context": data # Keep full JSON as context
        }

    def _normalize(self, data: Dict[str, str], fmt: str) -> Dict[str, Any]:
        """Normalizes regex matches to standard schema."""
        ts = datetime.now(timezone.utc)
        
        if fmt == "standard":
            ts = self._parse_timestamp(data["timestamp"], "%Y-%m-%d %H:%M:%S")
            return {
                "timestamp": ts,
                "severity": data["severity"],
                "service_name": data["service"], # Fixed key name from regex group
                "body": data["message"]
            }
            
        elif fmt == "syslog":
            # Syslog usually lacks year, assume current year
            ts_str = f"{datetime.now().year} {data['timestamp']}"
            ts = self._parse_timestamp(ts_str, "%Y %b %d %H:%M:%S")
            return {
                "timestamp": ts,
                "severity": "INFO", # Syslog doesn't always have severity in text
                "service_name": data["service"],
                "body": data["message"],
                "context": {"host": data["host"]}
            }
            
        elif fmt == "nginx":
            # 24/Nov/2025:16:00:00 +0000
            ts = self._parse_timestamp(data["timestamp"], "%d/%b/%Y:%H:%M:%S %z")
            return {
                "timestamp": ts,
                "severity": "INFO",
                "service_name": "nginx",
                "body": f"{data['request']} {data['status']}",
                "context": {
                    "client_ip": data["ip"],
                    "status": data["status"],
                    "bytes": data["bytes"]
                }
            }
            
        return {}

    def _parse_timestamp(self, ts_str: Optional[str], fmt: Optional[str] = None) -> datetime:
        """Helper to parse and normalize timestamp to UTC."""
        if not ts_str:
            return datetime.now(timezone.utc)
            
        try:
            if fmt:
                dt = datetime.strptime(ts_str, fmt)
            else:
                # ISO format fallback
                dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
                
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return datetime.now(timezone.utc)
