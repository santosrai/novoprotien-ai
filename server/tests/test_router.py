"""Tests for server.agents.router module."""
import pytest
from server.agents.router import SimpleRouterGraph


@pytest.fixture
def router():
    return SimpleRouterGraph()


# ---------------------------------------------------------------------------
# Rule-based routing tests (no embeddings needed)
# ---------------------------------------------------------------------------

class TestRuleBasedRouting:
    @pytest.mark.asyncio
    async def test_empty_input_routes_to_bio_chat(self, router):
        result = await router.ainvoke({"input": ""})
        assert result["routedAgentId"] == "bio-chat"
        assert "empty" in result["reason"]

    @pytest.mark.asyncio
    async def test_short_input_routes_to_bio_chat(self, router):
        result = await router.ainvoke({"input": "hi"})
        assert result["routedAgentId"] == "bio-chat"

    @pytest.mark.asyncio
    async def test_alphafold_fold_keyword(self, router):
        result = await router.ainvoke({"input": "fold this protein sequence"})
        assert result["routedAgentId"] == "alphafold-agent"
        assert "alphafold" in result["reason"]

    @pytest.mark.asyncio
    async def test_alphafold_dock_keyword(self, router):
        result = await router.ainvoke({"input": "dock protein A with protein B"})
        assert result["routedAgentId"] == "alphafold-agent"

    @pytest.mark.asyncio
    async def test_diffdock_ligand_docking(self, router):
        result = await router.ainvoke({"input": "dock this ligand to my protein"})
        assert result["routedAgentId"] == "diffdock-agent"
        assert "diffdock" in result["reason"]

    @pytest.mark.asyncio
    async def test_diffdock_protein_ligand_keyword(self, router):
        result = await router.ainvoke({"input": "run protein-ligand docking"})
        assert result["routedAgentId"] == "diffdock-agent"

    @pytest.mark.asyncio
    async def test_alphafold_predict_structure(self, router):
        result = await router.ainvoke({"input": "predict 3d structure of this protein"})
        assert result["routedAgentId"] == "alphafold-agent"

    @pytest.mark.asyncio
    async def test_rfdiffusion_design_keyword(self, router):
        result = await router.ainvoke({"input": "design a new protein"})
        assert result["routedAgentId"] == "rfdiffusion-agent"
        assert "rfdiffusion" in result["reason"]

    @pytest.mark.asyncio
    async def test_rfdiffusion_explicit_keyword(self, router):
        result = await router.ainvoke({"input": "use rfdiffusion to generate a novel protein"})
        assert result["routedAgentId"] == "rfdiffusion-agent"

    @pytest.mark.asyncio
    async def test_proteinmpnn_inverse_folding(self, router):
        result = await router.ainvoke({"input": "run proteinmpnn on this structure"})
        assert result["routedAgentId"] == "proteinmpnn-agent"

    @pytest.mark.asyncio
    async def test_proteinmpnn_sequence_design_with_structure(self, router):
        result = await router.ainvoke({"input": "design sequence for this backbone structure"})
        assert result["routedAgentId"] == "proteinmpnn-agent"

    @pytest.mark.asyncio
    async def test_pipeline_creation(self, router):
        result = await router.ainvoke({"input": "create a pipeline for protein design"})
        assert result["routedAgentId"] == "pipeline-agent"
        assert "pipeline" in result["reason"]

    @pytest.mark.asyncio
    async def test_pipeline_build_workflow(self, router):
        result = await router.ainvoke({"input": "build a pipeline for protein analysis"})
        assert result["routedAgentId"] == "pipeline-agent"

    @pytest.mark.asyncio
    async def test_scaffold_routes_to_alphafold_due_to_fold_keyword(self, router):
        """'scaffold' contains 'fold' which matches AlphaFold rule first."""
        result = await router.ainvoke({"input": "scaffold around hotspots A50,A51"})
        assert result["routedAgentId"] == "alphafold-agent"

    @pytest.mark.asyncio
    async def test_uniprot_search(self, router):
        result = await router.ainvoke({"input": "search uniprot for hemoglobin"})
        assert result["routedAgentId"] == "uniprot-search"

    @pytest.mark.asyncio
    async def test_chain_question_routes_to_bio_chat(self, router):
        result = await router.ainvoke({"input": "what chains are in this structure?"})
        assert result["routedAgentId"] == "bio-chat"

    @pytest.mark.asyncio
    async def test_selection_with_interrogative(self, router):
        result = await router.ainvoke({
            "input": "what is this residue?",
            "selection": {"kind": "residue", "compId": "GLU"},
        })
        assert result["routedAgentId"] == "bio-chat"
        assert "selection" in result["reason"]


class TestPipelineContextRouting:
    @pytest.mark.asyncio
    async def test_pipeline_context_question(self, router):
        result = await router.ainvoke({
            "input": "what is happening in this pipeline?",
            "pipeline_id": "pipe-123",
        })
        assert result["routedAgentId"] == "bio-chat"
        assert "pipeline-context" in result["reason"]

    @pytest.mark.asyncio
    async def test_pipeline_context_describe(self, router):
        result = await router.ainvoke({
            "input": "describe this pipeline",
            "pipeline_id": "pipe-123",
        })
        assert result["routedAgentId"] == "bio-chat"


class TestHeuristicFallback:
    @pytest.mark.asyncio
    async def test_code_builder_for_visualization(self, router):
        result = await router.ainvoke({"input": "show me this protein in cartoon representation"})
        assert result["routedAgentId"] == "code-builder"

    @pytest.mark.asyncio
    async def test_mvs_builder_for_labels(self, router):
        result = await router.ainvoke({"input": "annotate the binding site with labels"})
        assert result["routedAgentId"] == "mvs-builder"

    @pytest.mark.asyncio
    async def test_bio_chat_for_general_questions(self, router):
        result = await router.ainvoke({"input": "tell me about hemoglobin"})
        assert result["routedAgentId"] == "bio-chat"
