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
    For the prototype, this uses regex/heuristic matching.
    In production, this would use an LLM.
    """
    def __init__(self):
        self.db = DuckDBConnector()
        self.llm = LLMClient()
        self.prompts = PromptFactory()

    def generate_sql(self, query: str) -> Optional[str]:
        """Generates SQL from a natural language query using LLM."""
        try:
            prompt = self.prompts.create_prompt(
                "pilot_orchestrator", 
                "sql_generator", 
                query=query
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
            results = self.db.query(sql)
            return results
        except Exception as e:
            return [{"error": f"SQL Execution failed: {e}"}]
