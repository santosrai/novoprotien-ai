"""LangChain tool: open RFdiffusion protein design dialog."""

from __future__ import annotations

import json

try:
    from langchain_core.tools import tool
except ImportError:
    tool = None


def get_rfdiffusion_tool():
    """Return a LangChain tool that opens the RFdiffusion dialog."""
    if tool is None:
        raise RuntimeError("langchain_core.tools is required")

    @tool
    def open_rfdiffusion_dialog() -> str:
        """Open the RFdiffusion protein design dialog.
        Use when the user wants to design a new protein, create a protein,
        scaffold around motifs, do de novo design, or use RFdiffusion."""
        return json.dumps({"action": "open_rfdiffusion_dialog"})

    return open_rfdiffusion_dialog
