"""
Example demonstrating the official LangGraph pattern from documentation.
This shows the exact pattern: StateGraph, START, TypedDict state, add_node, add_edge, compile, invoke.
"""

from langgraph.graph import StateGraph, START, END
from typing import TypedDict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define state using TypedDict (official pattern)
class State(TypedDict):
    """State schema for the graph."""
    messages: list  # Example: list of messages
    # Add other state fields as needed


def ask_llm(state: State) -> State:
    """
    Node function that processes the state.
    In the official pattern, nodes return State updates (dict).
    """
    # Example: process messages
    user_query = state.get("messages", [])[-1] if state.get("messages") else "Hello"
    
    # In real implementation, you would call your LLM here
    # For example: answer_message = model.invoke([HumanMessage(user_query)])
    
    print(f"Processing query: {user_query}")
    
    # Return state updates (dict that will be merged into state)
    return {
        "messages": state.get("messages", []) + [f"Processed: {user_query}"]
    }


def build_example_graph():
    """
    Build graph using official LangGraph pattern:
    1. Create StateGraph with TypedDict state
    2. Add nodes with add_node()
    3. Add edges with add_edge() using START and END
    4. Compile with compile()
    """
    # Step 1: Create graph with state schema
    graph = StateGraph(State)
    
    # Step 2: Add nodes
    graph.add_node("ask_llm", ask_llm)
    
    # Step 3: Add edges
    graph.add_edge(START, "ask_llm")  # Start -> ask_llm
    graph.add_edge("ask_llm", END)   # ask_llm -> End
    
    # Step 4: Compile
    workflow = graph.compile()
    
    return workflow


if __name__ == "__main__":
    # Build the graph
    workflow = build_example_graph()
    
    # Optional: Visualize the graph
    try:
        with open("graph_example.png", "wb") as f:
            f.write(workflow.get_graph().draw_mermaid_png())
        print("Graph visualization saved to graph_example.png")
    except Exception as e:
        print(f"Could not generate graph visualization: {e}")
    
    # Invoke the workflow (official pattern)
    initial_state = {
        "messages": ["Hello, world!"]
    }
    
    # Use invoke() for sync or ainvoke() for async
    final_state = workflow.invoke(initial_state, {"recursion_limit": 100})
    
    print("Final state:", final_state)
