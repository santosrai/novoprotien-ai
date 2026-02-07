"""Tests for server.agents.registry module."""
import pytest
from server.agents.registry import agents, list_agents


class TestAgentRegistry:
    def test_registry_has_expected_agents(self):
        expected_ids = [
            "code-builder",
            "mvs-builder",
            "bio-chat",
            "uniprot-search",
            "alphafold-agent",
            "openfold2-agent",
            "rfdiffusion-agent",
            "proteinmpnn-agent",
            "pipeline-agent",
        ]
        for agent_id in expected_ids:
            assert agent_id in agents, f"Agent '{agent_id}' missing from registry"

    def test_each_agent_has_required_fields(self):
        required_fields = ["id", "name", "description", "system", "kind"]
        for agent_id, agent in agents.items():
            for field in required_fields:
                assert field in agent, f"Agent '{agent_id}' missing field '{field}'"

    def test_agent_ids_match_keys(self):
        for key, agent in agents.items():
            assert key == agent["id"], f"Key '{key}' != agent id '{agent['id']}'"

    def test_agent_descriptions_are_not_empty(self):
        for agent_id, agent in agents.items():
            # uniprot-search has an empty system prompt, but description should exist
            assert agent["description"], f"Agent '{agent_id}' has empty description"

    def test_agent_kinds_are_valid(self):
        valid_kinds = {"code", "text", "alphafold", "openfold2", "rfdiffusion", "proteinmpnn", "pipeline"}
        for agent_id, agent in agents.items():
            assert agent["kind"] in valid_kinds, (
                f"Agent '{agent_id}' has unexpected kind '{agent['kind']}'"
            )


class TestListAgents:
    def test_returns_list(self):
        result = list_agents()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_each_entry_has_required_fields(self):
        required = {"id", "name", "description", "kind", "category"}
        for entry in list_agents():
            assert required.issubset(set(entry.keys())), (
                f"Agent '{entry.get('id')}' list entry missing fields: "
                f"{required - set(entry.keys())}"
            )

    def test_does_not_expose_system_prompts(self):
        """list_agents should not include the full system prompt."""
        for entry in list_agents():
            assert "system" not in entry

    def test_agent_count_matches_registry(self):
        assert len(list_agents()) == len(agents)

    def test_categories_are_present(self):
        categories = {entry["category"] for entry in list_agents()}
        # At minimum we expect these categories
        expected = {"code", "ask", "fold", "design", "workflow"}
        assert expected.issubset(categories), (
            f"Missing categories: {expected - categories}"
        )
