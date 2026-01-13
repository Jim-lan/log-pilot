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
            
            # Clean up markdown if present
            sql = sql.replace("```sql", "").replace("```", "").strip()
            return sql
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
