"""
Test to verify the main graph follows the official LangGraph documentation pattern.

This test ensures we're using the correct imports, patterns, and API from langgraph.graph.
"""

import pytest


def test_main_graph_uses_official_imports():
    """Verify we're using the official LangGraph imports."""
    try:
        from langgraph.graph import StateGraph, START, END
    except ImportError:
        pytest.skip("langgraph not installed")
    
    # Verify imports are correct
    assert StateGraph is not None
    assert START is not None
    assert END is not None


def test_main_graph_uses_typeddict_state():
    """Verify state is defined using TypedDict (official pattern)."""
    from server.agents.graph_state import AgentGraphState
    from typing import TypedDict
    
    # Verify AgentGraphState is a TypedDict
    assert issubclass(AgentGraphState, TypedDict)


def test_build_main_graph_follows_official_pattern():
    """
    Verify build_main_graph follows the official LangGraph pattern:
    1. StateGraph(State)
    2. graph.add_node()
    3. graph.add_edge(START, ...)
    4. graph.add_edge(..., END)
    5. graph.compile()
    """
    try:
        from langgraph.graph import StateGraph, START, END
    except ImportError:
        pytest.skip("langgraph not installed")
    
    from server.agents.main_graph import build_main_graph
    from server.agents.graph_state import AgentGraphState
    
    # Build the graph
    workflow = build_main_graph()
    
    # Verify it's compiled (has invoke/ainvoke methods)
    assert hasattr(workflow, "invoke") or hasattr(workflow, "ainvoke")
    
    # Verify graph structure can be inspected
    graph = workflow.get_graph()
    assert graph is not None
    
    # Verify nodes exist
    nodes = graph.nodes
    assert "router" in nodes
    assert "agent" in nodes


def test_graph_can_be_invoked():
    """Verify the compiled graph can be invoked (official pattern: workflow.invoke/ainvoke)."""
    try:
        from langgraph.graph import StateGraph
    except ImportError:
        pytest.skip("langgraph not installed")
    
    from server.agents.main_graph import build_main_graph
    
    workflow = build_main_graph()
    
    # Verify invoke methods exist (official pattern)
    assert hasattr(workflow, "invoke") or hasattr(workflow, "ainvoke")


def test_graph_can_be_visualized():
    """Verify graph can generate visualization (official pattern: workflow.get_graph().draw_mermaid_png())."""
    try:
        from langgraph.graph import StateGraph
    except ImportError:
        pytest.skip("langgraph not installed")
    
    from server.agents.main_graph import build_main_graph
    
    workflow = build_main_graph()
    graph = workflow.get_graph()
    
    # Verify visualization method exists (official pattern)
    assert hasattr(graph, "draw_mermaid_png") or hasattr(graph, "draw_ascii")


def test_conditional_edges_follow_pattern():
    """Verify conditional edges use the official pattern (function returning node name or END)."""
    from server.agents.main_graph import _should_route_to_agent
    from langgraph.graph import END
    
    # Test conditional function returns string node name or END
    state_with_agent = {"routed_agent_id": "test-agent"}
    result = _should_route_to_agent(state_with_agent)
    assert result == "agent"  # Returns node name
    
    state_without_agent = {}
    result = _should_route_to_agent(state_without_agent)
    assert result == END  # Returns END constant
