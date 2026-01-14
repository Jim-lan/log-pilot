import re
from typing import List, Dict, Any, Optional
import sys
import os

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shared.db.duckdb_client import DuckDBConnector
from shared.llm.client import LLMClient
from shared.llm.prompt_factory import PromptFactory

class SQLGenerator:
    """
    Translates natural language queries into SQL for DuckDB.
    Uses an LLM (via LLMClient) and a Jinja2 template (via PromptFactory) to generate valid SQL.
    """
    def __init__(self):
        # self.db removed to avoid persistent connection
        self.llm = LLMClient()
        self.prompts = PromptFactory()

    def generate_sql(self, query: str, chat_history: str = "") -> Optional[str]:
        """Generates SQL from a natural language query using LLM."""
        try:
            prompt = self.prompts.create_prompt(
                "pilot_orchestrator", 
                "sql_generator", 
                query=query,
                chat_history=chat_history
            )
            sql = self.llm.generate(prompt, model_type="fast")
            
            # Robust extraction of SQL block or raw SQL
            import re
            
            # 1. Try to find markdown block
            match = re.search(r"```sql(.*?)```", sql, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
            
            match = re.search(r"```(.*?)```", sql, re.DOTALL)
            if match:
                 return match.group(1).strip()
            
            # 2. Heuristic: Look for SELECT/SHOW/DESCRIBE starting line
            # This is a fallback if no markdown is used
            match = re.search(r"(SELECT|SHOW|DESCRIBE|WITH|VALUES|INSERT|UPDATE|DELETE).*?($|;)", sql, re.DOTALL | re.IGNORECASE)
            if match:
                 # Return the string starting from the SQL keyword
                 # We grab the full match which might be the whole rest of string if no ;
                 # But re.search finds the *first* occurrence. 
                 # Let's take the substring from start of match to end of string to be safe against multi-line
                 start_idx = match.start()
                 return sql[start_idx:].strip()

            return sql.strip()
        except Exception as e:
            print(f"❌ SQL Generation Failed: {e}")
            return None

    def execute(self, query: str) -> List[Any]:
        """Generates and executes SQL."""
        sql = self.generate_sql(query)
        if not sql:
            return [{"error": "Could not understand query. Try 'count errors' or 'show recent logs'."}]
        
        print(f"🤖 Generated SQL: {sql}")
        try:
            # Use short-lived connection
            db = DuckDBConnector(read_only=True)
            try:
                results = db.query(sql)
                return results
            finally:
                db.close()
        except Exception as e:
            return [{"error": f"SQL Execution failed: {e}"}]
