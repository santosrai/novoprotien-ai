"""
Router stub: routing is now done by the ReAct agent via LLM tool calling.
This module is kept for backward compatibility (init_router, routerGraph).
"""

from __future__ import annotations

from typing import Any, Dict, List

try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):
        def noop(f):
            return f
        return noop


class SimpleRouterGraph:
    """Stub: no keyword or embedding routing. Use run_react_agent for chat."""

    async def ainit(self, agents: List[Dict[str, Any]]) -> None:
        """No-op. Kept for startup compatibility."""
        pass

    @traceable(name="RouterGraph.ainvoke", run_type="chain")
    async def ainvoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Always returns bio-chat. Callers should use run_react_agent instead."""
        return {"routedAgentId": "bio-chat", "reason": "react:no-routing"}


routerGraph = SimpleRouterGraph()


async def init_router(agents: List[Dict[str, Any]]) -> None:
    """Initialize router (no-op). Kept for startup compatibility."""
    await routerGraph.ainit(agents)
