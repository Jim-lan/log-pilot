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
    sql_valid: Optional[bool]
    sql_error: Optional[str]
    
    # RAG Path
    # RAG Path
    rag_context: Optional[str]
    web_results: Optional[str]
    
    # Final Output
    final_answer: Optional[str]
    
    # Metadata
    retry_count: int
    history: List[Dict[str, Any]]
    messages: List[Dict[str, str]] # Chat history for context
    rewritten_query: Optional[str] # Standalone query after rewriting
    
    # Verification
    context_valid: Optional[bool]
    context_feedback: Optional[str]
    answer_valid: Optional[bool]
    answer_feedback: Optional[str]
