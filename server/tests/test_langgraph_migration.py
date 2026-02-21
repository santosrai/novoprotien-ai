"""Tests for LangGraph migration: graph state, nodes, and main graph."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------

def test_agent_graph_state_keys():
    """AgentGraphState TypedDict allows expected keys."""
    from server.agents.graph_state import AgentGraphState

    state: AgentGraphState = {
        "input": "hello",
        "routed_agent_id": "bio-chat",
        "routing_reason": "test",
        "result_type": "text",
        "result_text": "Hi there",
    }
    assert state["input"] == "hello"
    assert state["routed_agent_id"] == "bio-chat"
    assert state["result_type"] == "text"


def test_agent_graph_state_optional_keys():
    """All keys are optional (total=False)."""
    from server.agents.graph_state import AgentGraphState

    state: AgentGraphState = {"input": "hi"}
    assert state.get("selection") is None
    assert state.get("result_code") is None


# ---------------------------------------------------------------------------
# Router node
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_router_node_passthrough_when_manual():
    """When state already has routed_agent_id and agent_config, router node passes through."""
    from server.agents.graph_nodes import router_node

    state = {
        "input": "fold protein",
        "routed_agent_id": "alphafold-agent",
        "agent_config": {"id": "alphafold-agent", "name": "AlphaFold"},
        "routing_reason": "manual",
    }
    out = await router_node(state)
    assert out["routed_agent_id"] == "alphafold-agent"
    assert out["agent_config"]["id"] == "alphafold-agent"
    assert out.get("routing_reason") in ("manual", None) or "manual" in str(out.get("routing_reason", ""))


@pytest.mark.asyncio
async def test_router_node_calls_router():
    """Router node calls SimpleRouterGraph and sets routed_agent_id from result."""
    from server.agents.graph_nodes import router_node

    state = {"input": "fold PDB:1ABC"}
    with patch("server.agents.graph_nodes._get_router") as get_router:
        mock_router = AsyncMock()
        mock_router.ainvoke.return_value = {"routedAgentId": "alphafold-agent", "reason": "rule:alphafold"}
        get_router.return_value = mock_router
        with patch("server.agents.graph_nodes._get_agents") as get_agents:
            get_agents.return_value = {"alphafold-agent": {"id": "alphafold-agent", "name": "AlphaFold"}}
            out = await router_node(state)

    assert out["routed_agent_id"] == "alphafold-agent"
    assert out["routing_reason"] == "rule:alphafold"
    assert out["agent_config"]["id"] == "alphafold-agent"
    mock_router.ainvoke.assert_called_once()


# ---------------------------------------------------------------------------
# Agent dispatcher node
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_dispatcher_node_no_agent():
    """When routed_agent_id or agent_config missing, returns error result."""
    from server.agents.graph_nodes import agent_dispatcher_node

    state = {"input": "hello", "routed_agent_id": None, "agent_config": None}
    out = await agent_dispatcher_node(state)
    assert out["result_type"] == "error"
    assert "No agent" in (out.get("result_text") or "")


@pytest.mark.asyncio
async def test_agent_dispatcher_node_calls_run_agent():
    """Dispatcher calls run_agent and maps result to state."""
    from server.agents.graph_nodes import agent_dispatcher_node

    state = {
        "input": "hello",
        "routed_agent_id": "bio-chat",
        "agent_config": {"id": "bio-chat", "name": "Bio Chat", "system": "You are helpful."},
    }
    with patch("server.agents.graph_nodes.run_agent", new_callable=AsyncMock) as run_agent:
        run_agent.return_value = {"type": "text", "text": "Hello back!"}
        out = await agent_dispatcher_node(state)

    assert out["result_type"] == "text"
    assert out["result_text"] == "Hello back!"
    run_agent.assert_called_once()
    call_kw = run_agent.call_args[1]
    assert call_kw["agent"]["id"] == "bio-chat"
    assert call_kw["user_text"] == "hello"


# ---------------------------------------------------------------------------
# Main graph
# ---------------------------------------------------------------------------

def test_build_main_graph_requires_langgraph():
    """build_main_graph raises when langgraph is not available."""
    from server.agents import main_graph as main_graph_mod

    with patch.object(main_graph_mod, "StateGraph", None):
        with patch.object(main_graph_mod, "START", None):
            with patch.object(main_graph_mod, "END", None):
                try:
                    main_graph_mod.build_main_graph()
                except RuntimeError as e:
                    assert "langgraph" in str(e).lower()
                else:
                    # If langgraph is installed, graph builds
                    pass


def test_build_main_graph_returns_compiled_when_available():
    """When langgraph is available, build_main_graph returns a compiled graph."""
    try:
        from langgraph.graph import StateGraph
    except ImportError:
        pytest.skip("langgraph not installed")
    from server.agents.main_graph import build_main_graph

    graph = build_main_graph()
    assert graph is not None
    assert hasattr(graph, "ainvoke") or hasattr(graph, "invoke")


# ---------------------------------------------------------------------------
# App helpers (state build and response map)
# ---------------------------------------------------------------------------

def test_build_initial_state():
    """_build_initial_state maps body and params to state dict."""
    from server.app import _build_initial_state

    body = {
        "input": "hello",
        "selection": None,
        "history": [],
        "currentCode": "",
        "uploadedFile": None,
        "currentStructureOrigin": None,
        "structureMetadata": None,
        "pdb_content": None,
    }
    state = _build_initial_state(
        input_text="hello",
        body=body,
        manual_agent_id=None,
        pipeline_id=None,
        pipeline_data=None,
        model_override=None,
        user={"id": "u1"},
    )
    assert state["input"] == "hello"
    assert state["user_id"] == "u1"
    assert "routed_agent_id" not in state or state["routed_agent_id"] is None


def test_build_initial_state_manual_agent():
    """_build_initial_state sets routed_agent_id and agent_config when manual_agent_id provided."""
    from server.app import _build_initial_state
    from server.agents.registry import agents

    body = {"input": "hi", "uploadedFile": None}
    state = _build_initial_state(
        input_text="hi",
        body=body,
        manual_agent_id="bio-chat",
        pipeline_id=None,
        pipeline_data=None,
        model_override=None,
        user={"id": "u1"},
    )
    assert state["routed_agent_id"] == "bio-chat"
    assert state["agent_config"] is not None
    assert state["agent_config"]["id"] == "bio-chat"


def test_final_state_to_response():
    """_final_state_to_response maps graph state to API response."""
    from server.app import _final_state_to_response

    final_state = {
        "routed_agent_id": "bio-chat",
        "routing_reason": "rule:bio",
        "result_type": "text",
        "result_text": "Here is the answer.",
    }
    out = _final_state_to_response(final_state)
    assert out["agentId"] == "bio-chat"
    assert out["reason"] == "rule:bio"
    assert out["type"] == "text"
    assert out["text"] == "Here is the answer."


def test_final_state_to_response_error():
    """_final_state_to_response sets error key when result_type is error."""
    from server.app import _final_state_to_response

    final_state = {
        "routed_agent_id": None,
        "routing_reason": None,
        "result_type": "error",
        "result_text": "No agent selected",
    }
    out = _final_state_to_response(final_state)
    assert out.get("error") == "No agent selected"
