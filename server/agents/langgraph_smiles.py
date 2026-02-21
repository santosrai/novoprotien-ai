"""
LangGraph-based agent with SMILES tool (official tool loop so the model reliably uses tools).
Flow: agent (with bind_tools) -> tools_condition -> ToolNode -> agent (no tools, summarize) -> END.

DEPRECATED: The runner now uses the unified LangChain agent layer (agents.langchain_agent + agents.llm + agents.tools.smiles).
This module is kept for reference and tests; invoke_smiles_graph is no longer called from run_agent.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any, Dict, List, Optional, Sequence, TypedDict

logger = logging.getLogger(__name__)

try:
    from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
    from langchain_core.tools import tool
    from langgraph.graph import END, START, StateGraph
    from langgraph.prebuilt import ToolNode, tools_condition
    from langgraph.graph.message import add_messages
    from langchain.chat_models import init_chat_model
except ImportError as e:
    logger.warning("LangGraph/LangChain imports failed: %s", e)
    tool = None
    StateGraph = None
    ToolNode = None
    tools_condition = None
    init_chat_model = None
    add_messages = None

try:
    from ..tools.smiles_converter import smiles_to_structure
except ImportError:
    from tools.smiles_converter import smiles_to_structure


def _make_smiles_langchain_tool():
    """Build the @tool used by LangGraph ToolNode."""
    @tool
    def show_smiles_in_viewer(smiles: str, format: str = "pdb") -> str:
        """Convert a SMILES string to a 3D structure (PDB or SDF) and show it in the molecular viewer.
        Use when the user provides a SMILES string and asks to show, display, or view it in 3D.

        Args:
            smiles: The SMILES string (e.g. O=C1NC2=C(N1)C(=O)NC(=O)N2). Extract exactly from the user message.
            format: Output format: 'pdb' or 'sdf'. Use 'pdb' unless the user explicitly asks for SDF.
        """
        fmt = (format or "pdb").lower()
        if fmt not in ("pdb", "sdf"):
            fmt = "pdb"
        try:
            content, filename = smiles_to_structure((smiles or "").strip(), fmt)
            return f"Successfully converted SMILES to 3D structure. Output file: {filename} ({len(content)} chars). The structure is ready to load in the viewer."
        except Exception as e:
            return f"Conversion failed: {e!s}"
    return show_smiles_in_viewer


# Lazy tool instance for the graph
_smiles_tool_instance: Optional[Any] = None


def _get_smiles_tool():
    global _smiles_tool_instance
    if _smiles_tool_instance is None:
        _smiles_tool_instance = _make_smiles_langchain_tool()
    return _smiles_tool_instance


def _messages_to_langchain(messages: List[Dict[str, Any]]) -> List[BaseMessage]:
    out: List[BaseMessage] = []
    for m in messages:
        role = (m.get("role") or "user").lower()
        content = m.get("content") or ""
        if role == "system":
            out.append(SystemMessage(content=content))
        elif role in ("user", "human"):
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
    return out


def _langchain_to_text_and_tool_calls(messages: Sequence[BaseMessage]) -> tuple[str, List[Any]]:
    """Get final assistant text (from last AIMessage) and all tool_calls from any AIMessage."""
    text = ""
    all_tool_calls: List[Any] = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            if msg.content:
                text = msg.content if isinstance(msg.content, str) else str(msg.content)
            if getattr(msg, "tool_calls", None):
                all_tool_calls.extend(msg.tool_calls or [])
    return text, all_tool_calls


def _tool_call_to_openrouter_format(tc: Any) -> Dict[str, Any]:
    """Convert LangChain tool_call to OpenRouter-style dict for process_smiles_tool_calls."""
    if isinstance(tc, dict):
        return tc
    args = getattr(tc, "args", None) or {}
    if not isinstance(args, str):
        args = json.dumps(args)
    return {
        "id": getattr(tc, "id", ""),
        "type": "function",
        "function": {
            "name": getattr(tc, "name", ""),
            "arguments": args,
        },
    }


def build_smiles_graph(model_id: str, api_key: Optional[str] = None):
    """Build and compile the LangGraph: agent (with tools) -> tools -> agent (summarize) -> END."""
    if StateGraph is None or ToolNode is None or tools_condition is None or init_chat_model is None:
        raise RuntimeError("langgraph and langchain (init_chat_model) are required for SMILES tool graph")

    import os
    key = (api_key or os.getenv("OPENROUTER_API_KEY") or "").strip()
    kwargs: Dict[str, Any] = dict(
        model=model_id,
        model_provider="openai",
        base_url="https://openrouter.ai/api/v1",
        api_key=key or None,
        temperature=0.5,
        max_tokens=1000,
    )
    llm = init_chat_model(**kwargs)
    tools = [_get_smiles_tool()]
    llm_with_tools = llm.bind_tools(tools)

    # State: messages (append-only via add_messages)
    class State(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]

    def agent_with_tools(state: State) -> Dict[str, Any]:
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    def agent_final(state: State) -> Dict[str, Any]:
        """After tool execution, get final answer from model (no tools)."""
        response = llm.invoke(state["messages"])
        return {"messages": [response]}

    tool_node = ToolNode(tools)
    graph = StateGraph(State)
    graph.add_node("agent", agent_with_tools)
    graph.add_node("tools", tool_node)
    graph.add_node("agent_final", agent_final)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent_final")
    graph.add_edge("agent_final", END)
    return graph.compile()


def invoke_smiles_graph(
    messages: List[Dict[str, Any]],
    model_id: str,
    api_key: Optional[str] = None,
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Run the LangGraph SMILES agent. Returns (final_text, tool_results for frontend).
    tool_results is a list of {"name": "show_smiles_in_viewer", "result": {"content": ..., "filename": ...}}.
    """
    try:
        from ..agents.smiles_tool import process_tool_calls
    except ImportError:
        from agents.smiles_tool import process_tool_calls

    graph = build_smiles_graph(model_id, api_key=api_key)
    lc_messages = _messages_to_langchain(messages)
    config = {"recursion_limit": 25}
    final_state = graph.invoke({"messages": lc_messages}, config=config)
    out_messages = final_state.get("messages") or []

    text, tool_calls_lc = _langchain_to_text_and_tool_calls(out_messages)
    tool_results = []
    if tool_calls_lc:
        # Convert to OpenRouter-style and run our executor to get content/filename for frontend
        openrouter_style = [_tool_call_to_openrouter_format(tc) for tc in tool_calls_lc]
        tool_results = process_tool_calls(openrouter_style)
    return text, tool_results
