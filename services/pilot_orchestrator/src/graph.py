from langgraph.graph import StateGraph, END
from services.pilot_orchestrator.src.state import AgentState
from services.pilot_orchestrator.src.nodes import (
    classify_intent,
    generate_sql,
    execute_sql,
    retrieve_context,
    synthesize_answer
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

def should_retry_sql(state: AgentState):
    """
    Conditional edge logic for SQL retry loop.
    """
    error = state.get("sql_error")
    retry_count = state.get("retry_count", 0)
    
    if error and retry_count < 3:
        return "generate_sql" # Retry
    return "synthesize_answer" # Proceed (with error message) or Success

# Define the Graph
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("classify_intent", classify_intent)
workflow.add_node("generate_sql", generate_sql)
workflow.add_node("execute_sql", execute_sql)
workflow.add_node("retrieve_context", retrieve_context)
workflow.add_node("synthesize_answer", synthesize_answer)

# Set Entry Point
workflow.set_entry_point("classify_intent")

# Add Edges
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

# 2. SQL Path
workflow.add_edge("generate_sql", "execute_sql")
workflow.add_conditional_edges(
    "execute_sql",
    should_retry_sql,
    {
        "generate_sql": "generate_sql", # Loop back
        "synthesize_answer": "synthesize_answer"
    }
)

# 3. RAG Path
workflow.add_edge("retrieve_context", "synthesize_answer")

# 4. End
workflow.add_edge("synthesize_answer", END)

# Compile
pilot_graph = workflow.compile()
