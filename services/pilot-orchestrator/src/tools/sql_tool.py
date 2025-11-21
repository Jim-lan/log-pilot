import re
from typing import List, Dict, Any, Optional
import sys
import os

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shared.db_connectors import DuckDBConnector

class SQLGenerator:
    """
    Translates natural language queries into SQL for DuckDB.
    For the prototype, this uses regex/heuristic matching.
    In production, this would use an LLM.
    """
    def __init__(self):
        self.db = DuckDBConnector()

    def generate_sql(self, query: str) -> Optional[str]:
        """Generates SQL from a natural language query."""
        query = query.lower()
        
        # Pattern 1: Count errors
        # "How many errors?" "Count all failures"
        if "count" in query or "how many" in query:
            if "error" in query or "fail" in query:
                return "SELECT count(*) as error_count FROM logs WHERE severity='ERROR'"
            return "SELECT count(*) as total_logs FROM logs"

        # Pattern 2: Show recent logs
        # "Show me the last 5 logs" "Recent logs"
        if "recent" in query or "last" in query:
            limit = 5
            # Extract number if present
            match = re.search(r'\d+', query)
            if match:
                limit = int(match.group())
            return f"SELECT timestamp, severity, service_name, body FROM logs ORDER BY timestamp DESC LIMIT {limit}"

        # Pattern 3: Filter by Service
        # "Show errors for payment-service"
        if "service" in query:
            # Extract service name (heuristic: word before or after 'service')
            # Simple regex to find 'payment-service' or 'auth-service'
            match = re.search(r'([a-z-]+-service)', query)
            if match:
                service = match.group(1)
                severity_clause = "AND severity='ERROR'" if "error" in query or "fail" in query else ""
                return f"SELECT timestamp, severity, body FROM logs WHERE service_name='{service}' {severity_clause} ORDER BY timestamp DESC LIMIT 10"

        return None

    def execute(self, query: str) -> List[Any]:
        """Generates and executes SQL."""
        sql = self.generate_sql(query)
        if not sql:
            return [{"error": "Could not understand query. Try 'count errors' or 'show recent logs'."}]
        
        print(f"🤖 Generated SQL: {sql}")
        try:
            results = self.db.query(sql)
            return results
        except Exception as e:
            return [{"error": f"SQL Execution failed: {e}"}]
