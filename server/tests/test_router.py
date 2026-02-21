"""Tests for server.agents.router module.

Routing is now done by the ReAct agent via LLM tool calling (no keyword matching).
The router is a stub for backward compatibility and always returns bio-chat.
"""

import pytest
from server.agents.router import SimpleRouterGraph


@pytest.fixture
def router():
    return SimpleRouterGraph()


class TestRouterStub:
    """Router is a stub; ainvoke always returns bio-chat with reason react:no-routing."""

    @pytest.mark.asyncio
    async def test_ainvoke_returns_bio_chat(self, router):
        result = await router.ainvoke({"input": ""})
        assert result["routedAgentId"] == "bio-chat"
        assert "react" in result["reason"] or "no-routing" in result["reason"]

    @pytest.mark.asyncio
    async def test_any_input_returns_bio_chat(self, router):
        result = await router.ainvoke({"input": "fold this protein sequence"})
        assert result["routedAgentId"] == "bio-chat"

    @pytest.mark.asyncio
    async def test_ainit_no_op(self, router):
        await router.ainit([{"id": "bio-chat", "name": "Test", "description": "Test"}])
        result = await router.ainvoke({"input": "hello"})
        assert result["routedAgentId"] == "bio-chat"
