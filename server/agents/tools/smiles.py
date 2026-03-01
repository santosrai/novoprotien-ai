"""
LangChain @tool for SMILES to 3D structure (show in viewer).
Used by bio-chat and code-builder agents via the LangChain agent layer.
"""

from __future__ import annotations

from typing import Any, Optional

try:
    from langchain_core.tools import tool
except ImportError:
    tool = None

try:
    from ...tools.smiles_converter import smiles_to_structure
except ImportError:
    from tools.smiles_converter import smiles_to_structure

_smiles_tool_instance: Optional[Any] = None


def get_smiles_tool() -> Any:
    """Return the LangChain tool instance for show_smiles_in_viewer (lazy singleton)."""
    global _smiles_tool_instance
    if _smiles_tool_instance is None:
        if tool is None:
            raise RuntimeError("langchain_core.tools is required for SMILES tool")
        _smiles_tool_instance = _make_smiles_tool()
    return _smiles_tool_instance


def _make_smiles_tool() -> Any:
    """Build the @tool used by LangGraph ToolNode / LangChain agent."""

    @tool
    def show_smiles_in_viewer(smiles: str, format: str = "sdf") -> str:
        """Convert a SMILES string to a 3D structure (PDB or SDF) and show it in the molecular viewer.
        Use when the user provides a SMILES string and asks to show, display, or view it in 3D.

        Args:
            smiles: The SMILES string (e.g. O=C1NC2=C(N1)C(=O)NC(=O)N2). Extract exactly from the user message.
            format: Output format: 'pdb' or 'sdf'. Use 'sdf' by default unless the user explicitly asks for PDB.
        """
        # Enforce SDF output for viewer/download consistency.
        fmt = "sdf"
        try:
            content, filename = smiles_to_structure((smiles or "").strip(), fmt)
            return (
                f"Successfully converted SMILES to 3D structure. Output file: {filename} ({len(content)} chars). "
                "The structure is ready to load in the viewer."
            )
        except Exception as e:
            return f"Conversion failed: {e!s}"

    return show_smiles_in_viewer
