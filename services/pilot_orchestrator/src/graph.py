from langgraph.graph import StateGraph, END
from services.pilot_orchestrator.src.state import AgentState
from services.pilot_orchestrator.src.nodes import (
    classify_intent,
    generate_sql,
    execute_sql,
    retrieve_context,
    synthesize_answer,
    rewrite_query,
    validate_sql,
    fix_sql,
    verify_context,
    validate_answer
)

def route_intent(state: AgentState):
    """
    Conditional edge logic to route based on intent.
    """
    intent = state.get("intent")
    if intent == "sql":
        return "generate_sql"
    elif intent == "rag":
        return "retrieve_context"
    else:
        return "synthesize_answer" # Handle ambiguous or direct chat

def check_sql_validity(state: AgentState):
    """
    Conditional edge logic for SQL validation.
    """
    if state.get("sql_valid"):
        return "execute_sql"
    
    retry_count = state.get("retry_count", 0)
    if retry_count < 3:
        return "fix_sql"
    
    return "synthesize_answer" # Give up and explain error

def check_context_validity(state: AgentState):
    """
    Conditional edge logic for Context verification.
    """
    if state.get("context_valid", True): # Default to true if not set
        return "synthesize_answer"
        
    retry_count = state.get("retry_count", 0)
    if retry_count < 2: # Limit retries
        # If context is invalid, we might want to rewrite query again or just try retrieval again
        # For now, let's loop back to rewrite with feedback (if we supported feedback in rewrite)
        # Or just fail over to synthesize_answer to say "I couldn't find anything"
        return "rewrite_query" 
    
    return "synthesize_answer"

def check_answer_validity(state: AgentState):
    """
    Conditional edge logic for Final Answer validation.
    """
    if state.get("answer_valid", True):
        return END
        
    retry_count = state.get("retry_count", 0)
    if retry_count < 2:
        return "synthesize_answer" # Retry synthesis
        
    return END

# Define the Graph
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("rewrite_query", rewrite_query)
workflow.add_node("classify_intent", classify_intent)
workflow.add_node("generate_sql", generate_sql)
workflow.add_node("validate_sql", validate_sql)
workflow.add_node("fix_sql", fix_sql)
workflow.add_node("execute_sql", execute_sql)
workflow.add_node("retrieve_context", retrieve_context)
workflow.add_node("verify_context", verify_context)
workflow.add_node("synthesize_answer", synthesize_answer)
workflow.add_node("validate_answer", validate_answer)

# Set Entry Point
workflow.set_entry_point("rewrite_query")

# Add Edges
# 0. Rewriter -> Classifier
workflow.add_edge("rewrite_query", "classify_intent")

# 1. From Classifier -> Router
workflow.add_conditional_edges(
    "classify_intent",
    route_intent,
    {
        "generate_sql": "generate_sql",
        "retrieve_context": "retrieve_context",
        "synthesize_answer": "synthesize_answer"
    }
)

# 2. SQL Path (with Validation Loop)
workflow.add_edge("generate_sql", "validate_sql")
workflow.add_conditional_edges(
    "validate_sql",
    check_sql_validity,
    {
        "execute_sql": "execute_sql",
        "fix_sql": "fix_sql",
        "synthesize_answer": "synthesize_answer"
    }
)
workflow.add_edge("fix_sql", "validate_sql") # Loop back to validation
workflow.add_edge("execute_sql", "synthesize_answer")

# 3. RAG Path (with Verification Loop)
workflow.add_edge("retrieve_context", "verify_context")
workflow.add_conditional_edges(
    "verify_context",
    check_context_validity,
    {
        "synthesize_answer": "synthesize_answer",
        "rewrite_query": "rewrite_query"
    }
)

# 4. Final Validation Loop
workflow.add_edge("synthesize_answer", "validate_answer")
workflow.add_conditional_edges(
    "validate_answer",
    check_answer_validity,
    {
        END: END,
        "synthesize_answer": "synthesize_answer"
    }
)

# Compile
pilot_graph = workflow.compile()
