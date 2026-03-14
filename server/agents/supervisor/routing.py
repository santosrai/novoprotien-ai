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

IMPORTANT ROUTING RULES:
- If the user asks to DO multiple things in one message (e.g. "search X then show Y"), route to the MOST SPECIFIC agent for the primary action. Do NOT route to pipeline.
- Route to pipeline ONLY when the user explicitly wants to CREATE, BUILD, or DESIGN a reusable pipeline/workflow blueprint (e.g. "create a pipeline that connects RFdiffusion to ProteinMPNN").
- If the message mentions SMILES, 3D conversion, loading molecules, or visualization in ANY part of the request, prefer code_builder.
- If the message mentions UniProt search, protein info, or biological questions combined with visualization, prefer code_builder (it can handle both).

Agents:
- bio_chat: Protein Q&A, biological information, structure analysis, general questions, greetings, UniProt searches, structure validation. Also handles compound requests that combine information lookup with other tasks.
- code_builder: MolStar/MolViewSpec visualization code generation. Any request to show, display, visualize, view, render, or load a protein, molecule, PDB ID, or structure in 3D. Also handles highlighting residues, adding labels, molecular scene creation, SMILES to 3D conversion, rendering representations (cartoon, surface, ball-and-stick), and compound requests that end with visualization or 3D loading.
- pipeline: ONLY for explicitly creating, building, or designing reusable pipeline/workflow blueprints (DAG nodes). Use this ONLY when the user says "create a pipeline", "build a workflow", "design a pipeline", or similar explicit pipeline construction language. Do NOT use for users who simply ask to do multiple things in sequence.
- alphafold: Fold a protein, predict protein structure, run AlphaFold, structure prediction from a sequence. Also handles UniProt accession structure prediction (e.g. "predict the structure of Q9HBE4", "fold P00533").
- openfold: Run OpenFold or OpenFold2 structure prediction.
- rfdiffusion: Design a new protein, de novo protein design, scaffold design, run RFdiffusion.
- proteinmpnn: Design sequences for a protein backbone, run ProteinMPNN, inverse folding, sequence design.
- diffdock: Dock a ligand to a protein, protein-ligand docking, predict binding pose, run DiffDock.
- alignment: Compare two protein structures, align structures, overlay structures, superpose proteins, TM-align, structural alignment, structure comparison.
- af2bind: Predict ligand-binding sites, binding site prediction, run AF2Bind, identify where ligands bind on a protein, binding residues.

Respond with ONLY the agent name: bio_chat, code_builder, pipeline, alphafold, openfold, rfdiffusion, proteinmpnn, diffdock, alignment, or af2bind"""

VALID_AGENTS = {"bio_chat", "code_builder", "pipeline", "alphafold", "openfold", "rfdiffusion", "proteinmpnn", "diffdock", "alignment", "af2bind"}


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
