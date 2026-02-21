"""
Main LangGraph agent routing graph: router -> agent dispatcher -> END.

This implementation follows the official LangGraph documentation pattern:
- Uses StateGraph from langgraph.graph
- Uses START and END constants from langgraph.graph
- Uses TypedDict for state definition (AgentGraphState)
- Uses graph.add_node() to add nodes
- Uses graph.add_edge() and graph.add_conditional_edges() for routing
- Uses graph.compile() to create the executable workflow

Example usage (official pattern):
    from langgraph.graph import StateGraph, START, END
    from typing import TypedDict
    
    class State(TypedDict):
        ...
    
    graph = StateGraph(State)
    graph.add_node("node_name", node_function)
    graph.add_edge(START, "node_name")
    graph.add_edge("node_name", END)
    workflow = graph.compile()
    result = await workflow.ainvoke(initial_state)
"""

from __future__ import annotations

from typing import Any

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:
    StateGraph = None  # type: ignore[misc, assignment]
    START = None
    END = None

from .graph_state import AgentGraphState
from .graph_nodes import router_node, agent_dispatcher_node


def _should_route_to_agent(state: AgentGraphState) -> str:
    """
    Conditional edge function: routes to agent node if agent is selected, otherwise END.
    
    This follows the official LangGraph pattern for conditional edges:
    - Returns a string node name or END constant
    - Used with graph.add_conditional_edges()
    """
    if state.get("routed_agent_id"):
        return "agent"
    return END


def build_main_graph() -> Any:
    """
    Build and compile the main agent routing graph using official LangGraph pattern.
    
    Pattern:
    1. Create StateGraph with TypedDict state schema
    2. Add nodes with add_node()
    3. Add edges with add_edge() using START/END constants
    4. Add conditional edges with add_conditional_edges()
    5. Compile with compile()
    
    Returns:
        Compiled workflow that can be invoked with workflow.ainvoke(state) or workflow.invoke(state)
    """
    if StateGraph is None:
        raise RuntimeError("langgraph is required for the main agent graph")

    # Step 1: Create graph with TypedDict state schema (official pattern)
    graph = StateGraph(AgentGraphState)
    
    # Step 2: Add nodes (official pattern)
    graph.add_node("router", router_node)
    graph.add_node("agent", agent_dispatcher_node)
    
    # Step 3: Add edges using START and END constants (official pattern)
    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", _should_route_to_agent)
    graph.add_edge("agent", END)
    
    # Step 4: Compile the graph (official pattern)
    return graph.compile()
