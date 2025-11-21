from typing import TypedDict, Optional, List, Dict, Any

class AgentState(TypedDict):
    """
    Represents the state of the Pilot Orchestrator agent.
    """
    query: str
    intent: Optional[str]  # "sql", "rag", "ambiguous"
    
    # SQL Path
    sql_query: Optional[str]
    sql_result: Optional[str]
    sql_error: Optional[str]
    
    # RAG Path
    rag_context: Optional[str]
    
    # Final Output
    final_answer: Optional[str]
    
    # Metadata
    retry_count: int
    history: List[Dict[str, Any]]
