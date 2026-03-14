"""
LangChain tools that return action JSON for the frontend (open dialog, etc.).
Used by the ReAct agent; the LLM calls these when the user intent matches the tool description.
"""

from __future__ import annotations

import json
from typing import Any

try:
    from langchain_core.tools import tool
except ImportError:
    tool = None


def _action_result(action: str, **kwargs: Any) -> str:
    """Return a JSON string the frontend can parse for action handling."""
    return json.dumps({"action": action, **kwargs})


def get_action_tools() -> list:
    """Return list of LangChain tools for opening dialogs and search. Requires langchain_core.tools."""
    if tool is None:
        raise RuntimeError("langchain_core.tools is required for action tools")

    @tool
    def open_alphafold_dialog() -> str:
        """Open the AlphaFold structure prediction dialog. Use when the user wants to fold a protein, predict structure, run AlphaFold, or predict 3D structure from a sequence."""
        return _action_result("open_alphafold_dialog")

    @tool
    def open_diffdock_dialog() -> str:
        """Open the DiffDock protein-ligand docking dialog. Use when the user wants to dock a ligand to a protein, run protein-ligand docking, predict binding pose, or bind a small molecule to a protein."""
        return _action_result("open_diffdock_dialog")

    @tool
    def open_openfold2_dialog() -> str:
        """Open the OpenFold2 structure prediction dialog. Use when the user wants to use OpenFold2, predict structure with OpenFold2, or has pre-computed MSA/template for structure prediction (max 1000 residues)."""
        return _action_result("open_openfold2_dialog")

    @tool
    def open_rfdiffusion_dialog() -> str:
        """Open the RFdiffusion protein design dialog. Use when the user wants to design a new protein, create a protein, scaffold around motifs, do de novo design, or use RFdiffusion."""
        return _action_result("open_rfdiffusion_dialog")

    return [
        open_alphafold_dialog,
        open_diffdock_dialog,
        open_openfold2_dialog,
        open_rfdiffusion_dialog,
    ]


def get_uniprot_tool() -> Any:
    """Return a LangChain tool that searches UniProt (async)."""
    if tool is None:
        raise RuntimeError("langchain_core.tools is required for UniProt tool")

    try:
        from ...domain.protein.uniprot import search_uniprot as _search_uniprot
    except ImportError:
        from domain.protein.uniprot import search_uniprot as _search_uniprot

    @tool
    async def search_uniprot(query: str, size: int = 5) -> str:
        """Search UniProt for proteins by name, gene, organism, or keyword. Returns a summary of matching entries (accession, name, organism, length). Use when the user asks to search UniProt, find a protein in UniProt, or look up a protein by name/gene."""
        items = await _search_uniprot(query, size=size)
        if not items:
            return "No UniProt entries found for that query."
        lines = [f"- {e.get('accession', '?')} ({e.get('protein', 'Unknown')}); {e.get('organism', '?')}; length {e.get('length', '?')}" for e in items]
        return "UniProt results:\n" + "\n".join(lines)

    return search_uniprot
