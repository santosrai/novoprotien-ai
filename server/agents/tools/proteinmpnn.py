"""LangChain tool: open ProteinMPNN sequence design dialog."""

from __future__ import annotations

import json

try:
    from langchain_core.tools import tool
except ImportError:
    tool = None


def get_proteinmpnn_tool():
    """Return a LangChain tool that opens the ProteinMPNN dialog."""
    if tool is None:
        raise RuntimeError("langchain_core.tools is required")

    @tool
    def open_proteinmpnn_dialog() -> str:
        """Open the ProteinMPNN sequence design dialog.
        Use when the user wants to design sequences for a protein backbone,
        inverse fold, redesign amino acid sequences, or use ProteinMPNN."""
        return json.dumps({"action": "open_proteinmpnn_dialog"})

    return open_proteinmpnn_dialog
