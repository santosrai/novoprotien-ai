"""
Agent factory: get_agent(agent_id, ...) for legacy per-agent graph; get_react_agent() for tool-calling ReAct.
ReAct uses one LLM with bind_tools(); the LLM decides when to call tools (no keyword routing).
"""

from __future__ import annotations

from typing import Any, Optional

from ..llm.model import get_chat_model
from ..registry import agents
from ..prompts.bio_chat import REACT_SYSTEM_PROMPT
from ..tools import get_all_react_tools
from ..tools.smiles import get_smiles_tool
from .graph import build_agent_graph


def get_react_agent(
    model_id: str,
    api_key: Optional[str] = None,
    *,
    temperature: float = 0.5,
    max_tokens: int = 1000,
) -> Any:
    """Build and return the ReAct agent graph: one LLM with all tools, tools_condition -> ToolNode loop.

    The LLM uses structured tool_calls (from bind_tools) to decide when to call tools;
    no keyword-based routing. Use this as the single entry point for chat.
    """
    llm = get_chat_model(
        model_id,
        api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    tools = get_all_react_tools()
    return build_agent_graph(llm, tools, system_prompt=REACT_SYSTEM_PROMPT)


def get_agent(
    agent_id: str,
    model_id: str,
    api_key: Optional[str] = None,
    *,
    temperature: float = 0.5,
    max_tokens: int = 1000,
) -> Any:
    """Build and return a compiled LangChain/LangGraph agent for the given agent_id and model.
    Legacy: used when a specific agent (e.g. code-builder only) is needed.
    """
    agent_config = agents.get(agent_id)
    if not agent_config:
        raise ValueError(f"Unknown agent_id: {agent_id}")

    tools = []
    if agent_id in ("bio-chat", "code-builder"):
        tools.append(get_smiles_tool())

    llm = get_chat_model(
        model_id,
        api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return build_agent_graph(llm, tools, system_prompt=agent_config.get("system"))
