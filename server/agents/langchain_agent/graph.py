"""
ReAct-style LangGraph: agent (bind_tools) -> tools_condition -> ToolNode -> agent (loop) -> END.
The LLM decides when to call tools via structured tool_calls; no keyword routing.
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional, Sequence, TypedDict

try:
    from langchain_core.messages import BaseMessage, SystemMessage
    from langgraph.graph import END, START, StateGraph
    from langgraph.prebuilt import ToolNode, tools_condition
    from langgraph.graph.message import add_messages
except ImportError:
    BaseMessage = None
    SystemMessage = None
    StateGraph = None
    START = None
    END = None
    ToolNode = None
    tools_condition = None
    add_messages = None


def build_agent_graph(
    llm: Any,
    tools: List[Any],
    *,
    system_prompt: Optional[str] = None,
) -> Any:
    """Build and compile the ReAct agent graph: agent <-> tools loop until no tool_calls.

    Flow:
    1. Agent node: LLM with bind_tools(tools) sees messages, may output AIMessage with tool_calls.
    2. tools_condition: if last message has tool_calls -> "tools", else END.
    3. Tool node: executes tools, appends ToolMessages.
    4. Edge tools -> agent: loop back so LLM can reason over tool results or call more tools.

    Args:
        llm: LangChain chat model (from get_chat_model).
        tools: List of LangChain tools; can be empty for no-tool agents.
        system_prompt: If provided, prepended as a SystemMessage before the
            input messages on every LLM call.  This ensures each sub-agent
            gets its own specialised prompt.

    Returns:
        Compiled graph with invoke({"messages": [...]}, config={"recursion_limit": 25}).
    """
    if StateGraph is None or ToolNode is None or tools_condition is None or add_messages is None:
        raise RuntimeError("langgraph is required for agent graph")

    llm_with_tools = llm.bind_tools(tools) if tools else llm
    _system_prompt = system_prompt

    class State(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]

    from langchain_core.runnables import RunnableConfig

    async def agent_node(state: State, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
        msgs = list(state["messages"])
        if _system_prompt and SystemMessage is not None:
            has_system = msgs and getattr(msgs[0], "type", None) == "system"
            if not has_system:
                msgs = [SystemMessage(content=_system_prompt)] + msgs
        response = await llm_with_tools.ainvoke(msgs, config=config or {})
        return {"messages": [response]}

    def _noop_tools(state: State) -> Dict[str, Any]:
        return {}  # no state update when no tools

    tool_node = ToolNode(tools) if tools else _noop_tools
    graph = StateGraph(State)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    # ReAct: agent -> tools_condition -> tools (then loop back to agent) or END
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")  # loop back to agent with tool results
    return graph.compile()
