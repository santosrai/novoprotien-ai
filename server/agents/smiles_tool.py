"""
OpenRouter tool definition and execution for SMILES-to-3D (show in viewer).
Used by bio-chat and code-builder agents when the model returns tool_calls.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

try:
    from ..tools.smiles_converter import smiles_to_structure
except ImportError:
    from tools.smiles_converter import smiles_to_structure

# OpenRouter/OpenAI function-calling format: single tool for SMILES to 3D
SHOW_SMILES_IN_VIEWER_TOOL = {
    "type": "function",
    "function": {
        "name": "show_smiles_in_viewer",
        "description": (
            "Convert a SMILES string to a 3D structure (PDB or SDF) and show it in the molecular viewer. "
            "Use when the user provides a SMILES string and asks to show, display, or view it in 3D."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "smiles": {
                    "type": "string",
                    "description": "The SMILES string (e.g. O=C1NC2=C(N1)C(=O)NC(=O)N2). Extract exactly from the user message.",
                },
                "format": {
                    "type": "string",
                    "enum": ["pdb", "sdf"],
                    "description": "Output format. Use 'pdb' unless the user explicitly asks for SDF.",
                    "default": "pdb",
                },
            },
            "required": ["smiles"],
        },
    },
}

# Payload for OpenRouter: tools array (one element)
SMILES_TOOLS_PAYLOAD = [SHOW_SMILES_IN_VIEWER_TOOL]


def execute_show_smiles_in_viewer(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the show_smiles_in_viewer tool from a single tool_call item.

    Args:
        tool_call: OpenRouter tool_call dict with function.name and function.arguments.

    Returns:
        Dict with either:
        - success: {"content": "<pdb or sdf string>", "filename": "..."}
        - error: {"error": "<user-friendly message>"}
    """
    name = (tool_call.get("function") or {}).get("name")
    if name != "show_smiles_in_viewer":
        return {"error": f"Unknown tool: {name}"}

    raw_args = (tool_call.get("function") or {}).get("arguments") or "{}"
    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    except json.JSONDecodeError as e:
        logger.warning("show_smiles_in_viewer: invalid arguments %s", e)
        return {"error": "Invalid tool arguments."}

    smiles = (args.get("smiles") or "").strip()
    if not smiles:
        return {"error": "SMILES string is required."}

    fmt = (args.get("format") or "pdb").lower()
    if fmt not in ("pdb", "sdf"):
        fmt = "pdb"

    try:
        content, filename = smiles_to_structure(smiles, fmt)
        return {"content": content, "filename": filename}
    except ValueError as e:
        return {"error": str(e)}
    except RuntimeError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("show_smiles_in_viewer execution failed")
        return {"error": "Failed to convert SMILES to structure."}


def process_tool_calls(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process a list of tool_calls from the OpenRouter response; run only show_smiles_in_viewer.

    Returns a list of { "name": str, "result": dict } for consumption by the runner/frontend.
    """
    results = []
    for tc in tool_calls or []:
        name = (tc.get("function") or {}).get("name")
        if name != "show_smiles_in_viewer":
            continue
        result = execute_show_smiles_in_viewer(tc)
        results.append({"name": name, "result": result})
    return results
