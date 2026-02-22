"""LangChain tool: open OpenFold2 structure prediction dialog."""

from __future__ import annotations

import json

try:
    from langchain_core.tools import tool
except ImportError:
    tool = None


def get_openfold_tool():
    """Return a LangChain tool that opens the OpenFold2 dialog."""
    if tool is None:
        raise RuntimeError("langchain_core.tools is required")

    @tool
    def open_openfold2_dialog() -> str:
        """Open the OpenFold2 structure prediction dialog.
        Use when the user wants to use OpenFold2, predict structure with OpenFold2,
        or has pre-computed MSA/template for structure prediction (max 1000 residues)."""
        return json.dumps({"action": "open_openfold2_dialog"})

    return open_openfold2_dialog
