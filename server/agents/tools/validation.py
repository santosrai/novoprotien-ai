"""LangChain tool: trigger protein structure validation."""

from __future__ import annotations

import json

try:
    from langchain_core.tools import tool
except ImportError:
    tool = None


def get_validation_tool():
    """Return a LangChain tool that triggers structure validation."""
    if tool is None:
        raise RuntimeError("langchain_core.tools is required")

    @tool
    def validate_structure(source: str = "current") -> str:
        """Validate a protein structure's quality.
        Use when the user asks to validate, check quality, assess structure,
        run quality report, check confidence scores, or Ramachandran analysis.

        Args:
            source: 'current' for viewer structure, 'file' for uploaded file.
        """
        return json.dumps({"action": "validate_structure", "source": source})

    return validate_structure
