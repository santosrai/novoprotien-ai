"""
OpenRouter dict <-> LangChain BaseMessage conversion and app result shaping.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence

try:
    from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
except ImportError:
    AIMessage = None  # type: ignore[misc, assignment]
    BaseMessage = None
    HumanMessage = None
    SystemMessage = None


def openrouter_to_langchain(messages: List[Dict[str, Any]]) -> List[BaseMessage]:
    """Convert OpenRouter-style message list to LangChain BaseMessage list."""
    if BaseMessage is None or HumanMessage is None or SystemMessage is None or AIMessage is None:
        raise RuntimeError("langchain_core.messages is required")
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


def _tool_call_to_openrouter_format(tc: Any) -> Dict[str, Any]:
    """Convert LangChain tool_call to OpenRouter-style dict for process_tool_calls."""
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


def langchain_to_app_text(
    messages: Sequence[BaseMessage],
) -> tuple[str, List[Dict[str, Any]]]:
    """Extract final assistant text and tool results for frontend from LangChain messages.

    Returns:
        (text, tool_results) where tool_results is list of {"name": str, "result": dict}.
    """
    if AIMessage is None:
        raise RuntimeError("langchain_core.messages is required")
    text = ""
    all_tool_calls: List[Any] = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            if msg.content:
                text = msg.content if isinstance(msg.content, str) else str(msg.content)
            if getattr(msg, "tool_calls", None):
                all_tool_calls.extend(msg.tool_calls or [])

    tool_results: List[Dict[str, Any]] = []
    if all_tool_calls:
        try:
            from ..smiles_tool import process_tool_calls
        except ImportError:
            from agents.smiles_tool import process_tool_calls
        openrouter_style = [_tool_call_to_openrouter_format(tc) for tc in all_tool_calls]
        tool_results = process_tool_calls(openrouter_style)

    return text, tool_results
