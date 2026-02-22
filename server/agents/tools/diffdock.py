"""LangChain tool: open DiffDock protein-ligand docking dialog."""

from __future__ import annotations

import json

try:
    from langchain_core.tools import tool
except ImportError:
    tool = None


def get_diffdock_tool():
    """Return a LangChain tool that opens the DiffDock dialog."""
    if tool is None:
        raise RuntimeError("langchain_core.tools is required")

    @tool
    def open_diffdock_dialog() -> str:
        """Open the DiffDock protein-ligand docking dialog.
        Use when the user wants to dock a ligand to a protein, run protein-ligand docking,
        predict binding pose, or bind a small molecule to a protein."""
        return json.dumps({"action": "open_diffdock_dialog"})

    return open_diffdock_dialog
