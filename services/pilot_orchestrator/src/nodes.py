import sys
import os
from typing import Dict, Any

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from services.pilot_orchestrator.src.state import AgentState
from shared.llm.client import LLMClient
from shared.llm.prompt_factory import PromptFactory
from services.pilot_orchestrator.src.tools.sql_tool import SQLGenerator
from services.knowledge_base.src.store import KnowledgeStore

# Initialize Shared Components
llm_client = LLMClient()
prompt_factory = PromptFactory()
sql_tool = SQLGenerator()
# Lazy load KnowledgeStore to avoid init issues during testing if not needed
_kb_store = None

def get_kb_store():
    global _kb_store
    if _kb_store is None:
        _kb_store = KnowledgeStore()
    return _kb_store

def classify_intent(state: AgentState) -> AgentState:
    """
    Determines if the user query requires SQL (data) or RAG (knowledge).
    """
    query = state["query"]
    # Simple heuristic for now, can be upgraded to LLM call
    if any(w in query.lower() for w in ["count", "how many", "list", "show", "select", "find"]):
        state["intent"] = "sql"
    elif any(w in query.lower() for w in ["why", "how to", "explain", "what is", "fix"]):
        state["intent"] = "rag"
    else:
        state["intent"] = "ambiguous"
    
    print(f"🤔 Intent Classified: {state['intent']}")
    return state

def generate_sql(state: AgentState) -> AgentState:
    """
    Generates SQL from natural language using the SQLGenerator tool.
    """
    query = state["query"]
    try:
        sql = sql_tool.generate_sql(query)
        state["sql_query"] = sql
        state["sql_error"] = None # Clear previous errors
    except Exception as e:
        state["sql_error"] = str(e)
    
    return state

def execute_sql(state: AgentState) -> AgentState:
    """
    Executes the generated SQL against DuckDB.
    """
    sql = state["sql_query"]
    if not sql:
        state["sql_error"] = "No SQL generated"
        return state

    try:
        # In a real app, we'd call DuckDBConnector here.
        # For now, using the mock execution from SQLGenerator or a placeholder.
        # result = db.execute(sql) 
        result = f"Mock Result for: {sql}" # Placeholder
        state["sql_result"] = result
    except Exception as e:
        state["sql_error"] = str(e)
        state["retry_count"] = state.get("retry_count", 0) + 1
    
    return state

def retrieve_context(state: AgentState) -> AgentState:
    """
    Queries the Knowledge Base for context.
    """
    query = state["query"]
    kb = get_kb_store()
    try:
        context = kb.query(query)
        state["rag_context"] = context
    except Exception as e:
        state["rag_context"] = f"Error retrieving context: {e}"
    
    return state

def synthesize_answer(state: AgentState) -> AgentState:
    """
    Generates the final answer using the LLM.
    """
    intent = state["intent"]
    query = state["query"]
    
    if intent == "sql":
        context = f"SQL: {state.get('sql_query')}\nResult: {state.get('sql_result')}"
        if state.get("sql_error"):
             context = f"SQL Error: {state['sql_error']}"
    elif intent == "rag":
        context = f"Retrieved Context: {state.get('rag_context')}"
    else:
        context = "Ambiguous intent."

    prompt = f"User Query: {query}\nContext: {context}\n\nProvide a helpful answer."
    response = llm_client.generate(prompt, model_type="fast")
    
    state["final_answer"] = response
    return state
