"""Supervisor routing: LLM-based agent selection."""

from __future__ import annotations

from typing import Any, Optional, Tuple

try:
    from langchain_core.messages import SystemMessage, HumanMessage
except ImportError:
    SystemMessage = None
    HumanMessage = None


SUPERVISOR_ROUTING_PROMPT = """You are a routing assistant for a molecular biology AI platform.
Given a user message, decide which specialist agent should handle it.

Agents:
- bio_chat: Protein Q&A, biological information, structure analysis, general questions, greetings, UniProt searches, structure validation.
- code_builder: MolStar/MolViewSpec visualization code generation. Any request to show, display, visualize, view, render, or load a protein, molecule, PDB ID, or structure in 3D. Also handles highlighting residues, adding labels, molecular scene creation, SMILES to 3D conversion, and rendering representations (cartoon, surface, ball-and-stick).
- pipeline: Workflow composition, creating pipelines connecting multiple tools, designing multi-step protein design workflows, building DAG workflows.
- alphafold: Fold a protein, predict protein structure, run AlphaFold, structure prediction from a sequence.
- openfold: Run OpenFold or OpenFold2 structure prediction.
- rfdiffusion: Design a new protein, de novo protein design, scaffold design, run RFdiffusion.
- proteinmpnn: Design sequences for a protein backbone, run ProteinMPNN, inverse folding, sequence design.
- diffdock: Dock a ligand to a protein, protein-ligand docking, predict binding pose, run DiffDock.

Respond with ONLY the agent name: bio_chat, code_builder, pipeline, alphafold, openfold, rfdiffusion, proteinmpnn, or diffdock"""

VALID_AGENTS = {"bio_chat", "code_builder", "pipeline", "alphafold", "openfold", "rfdiffusion", "proteinmpnn", "diffdock"}


async def route_to_agent(
    llm: Any,
    user_text: str,
    *,
    history: Optional[list] = None,
) -> Tuple[str, str]:
    """Use the LLM to decide which sub-agent handles this request.

    Returns:
        (agent_id, reason) tuple.
    """
    if SystemMessage is None or HumanMessage is None:
        return "bio_chat", "fallback:no_langchain"

    routing_messages = [
        SystemMessage(content=SUPERVISOR_ROUTING_PROMPT),
        HumanMessage(content=f"Route this request: {user_text}"),
    ]

    try:
        response = await llm.ainvoke(routing_messages)
        agent_id = response.content.strip().lower().replace("-", "_")
        for valid in VALID_AGENTS:
            if valid in agent_id:
                return valid, f"llm_routing:{valid}"
        return "bio_chat", f"llm_routing:fallback (raw={agent_id})"
    except Exception as e:
        print(f"[supervisor] routing error: {e}")
        return "bio_chat", f"error_fallback:{e}"
