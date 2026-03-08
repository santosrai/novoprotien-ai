"""
LangGraph nodes for the main agent routing graph: router and agent dispatcher.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from .graph_state import AgentGraphState

# Lazy imports to avoid circular dependency and allow router/registry to load first
_router_graph = None
_agents_registry = None


def _get_router():
    global _router_graph
    if _router_graph is None:
        from .router import routerGraph
        _router_graph = routerGraph
    return _router_graph


def _get_agents():
    global _agents_registry
    if _agents_registry is None:
        from .registry import agents
        _agents_registry = agents
    return _agents_registry


async def router_node(state: "AgentGraphState") -> Dict[str, Any]:
    """Router node: selects agent based on input and context. Reuses SimpleRouterGraph."""
    # Manual selection: if already routed (e.g. from app with manual_agent_id), pass through
    if state.get("routed_agent_id") and state.get("agent_config"):
        return {**state, "routing_reason": state.get("routing_reason") or "manual"}

    router = _get_router()
    agents_reg = _get_agents()

    router_input = {
        "input": state.get("input") or "",
        "selection": state.get("selection"),
        "selections": state.get("selections"),
        "currentCode": state.get("currentCode"),
        "history": state.get("history"),
        "pipeline_id": state.get("pipeline_id"),
        "uploadedFileId": state.get("uploadedFileId"),
        "pipelineContext": state.get("pipeline_data"),  # backward compatibility
    }
    routed = await router.ainvoke(router_input)

    agent_id = routed.get("routedAgentId")
    reason = routed.get("reason")
    agent_config = agents_reg.get(agent_id) if agent_id else None

    return {
        **state,
        "routed_agent_id": agent_id,
        "routing_reason": reason,
        "agent_config": agent_config,
    }


async def agent_dispatcher_node(state: "AgentGraphState") -> Dict[str, Any]:
    """Dispatch to the appropriate agent using existing run_agent()."""
    from .runner import run_agent

    agent_id = state.get("routed_agent_id")
    agent_config = state.get("agent_config")

    if not agent_id or not agent_config:
        return {
            **state,
            "result_type": "error",
            "result_text": "No agent selected",
        }

    result = await run_agent(
        agent=agent_config,
        user_text=state.get("input") or "",
        current_code=state.get("currentCode"),
        history=state.get("history"),
        selection=state.get("selection"),
        selections=state.get("selections"),
        current_structure_origin=state.get("currentStructureOrigin"),
        uploaded_file_context=state.get("uploadedFileContext"),
        structure_metadata=state.get("structureMetadata"),
        pipeline_id=state.get("pipeline_id"),
        pipeline_data=state.get("pipeline_data"),
        model_override=state.get("model_override"),
        user_id=state.get("user_id"),
        pdb_content=state.get("pdb_content"),
    )

    return {
        **state,
        "result_type": result.get("type", "text"),
        "result_text": result.get("text"),
        "result_code": result.get("code"),
        "tool_results": result.get("toolResults"),
        "thinking_process": result.get("thinkingProcess"),
    }
