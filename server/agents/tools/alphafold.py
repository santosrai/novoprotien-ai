"""LangChain tool: open AlphaFold structure prediction dialog."""

from __future__ import annotations

import json

try:
    from langchain_core.tools import tool
except ImportError:
    tool = None


def get_alphafold_tool():
    """Return a LangChain tool that opens the AlphaFold dialog."""
    if tool is None:
        raise RuntimeError("langchain_core.tools is required")

    @tool
    def open_alphafold_dialog() -> str:
        """Open the AlphaFold structure prediction dialog.
        Use when the user wants to fold a protein, predict structure,
        run AlphaFold, or predict 3D structure from a sequence."""
        return json.dumps({"action": "open_alphafold_dialog"})

    return open_alphafold_dialog
