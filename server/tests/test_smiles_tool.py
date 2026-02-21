"""Tests for server.agents.smiles_tool (OpenRouter tool definition and execution)."""
import json
import pytest
from unittest.mock import patch

from server.agents.smiles_tool import (
    SHOW_SMILES_IN_VIEWER_TOOL,
    SMILES_TOOLS_PAYLOAD,
    execute_show_smiles_in_viewer,
    process_tool_calls,
)


def test_tool_schema_shape():
    assert SHOW_SMILES_IN_VIEWER_TOOL["type"] == "function"
    fn = SHOW_SMILES_IN_VIEWER_TOOL["function"]
    assert fn["name"] == "show_smiles_in_viewer"
    assert "description" in fn
    params = fn["parameters"]
    assert params["type"] == "object"
    assert "smiles" in params["properties"]
    assert "format" in params["properties"]
    assert "smiles" in params["required"]


def test_smiles_tools_payload_is_list():
    assert isinstance(SMILES_TOOLS_PAYLOAD, list)
    assert len(SMILES_TOOLS_PAYLOAD) == 1
    assert SMILES_TOOLS_PAYLOAD[0] == SHOW_SMILES_IN_VIEWER_TOOL


def test_process_tool_calls_empty():
    assert process_tool_calls([]) == []
    assert process_tool_calls(None) == []


def test_process_tool_calls_unknown_tool_ignored():
    tool_calls = [
        {"function": {"name": "other_tool", "arguments": "{}"}},
    ]
    assert process_tool_calls(tool_calls) == []


def test_execute_show_smiles_in_viewer_missing_smiles():
    tc = {"function": {"name": "show_smiles_in_viewer", "arguments": "{}"}}
    out = execute_show_smiles_in_viewer(tc)
    assert "error" in out
    assert "SMILES" in out["error"]


def test_execute_show_smiles_in_viewer_invalid_args():
    tc = {"function": {"name": "show_smiles_in_viewer", "arguments": "not json"}}
    out = execute_show_smiles_in_viewer(tc)
    assert "error" in out


@patch("server.agents.smiles_tool.smiles_to_structure")
def test_process_tool_calls_smiles_success(mock_structure):
    mock_structure.return_value = ("CONTENT", "smiles_structure.pdb")
    tool_calls = [
        {
            "function": {
                "name": "show_smiles_in_viewer",
                "arguments": json.dumps({"smiles": "CCO", "format": "pdb"}),
            }
        },
    ]
    results = process_tool_calls(tool_calls)
    assert len(results) == 1
    assert results[0]["name"] == "show_smiles_in_viewer"
    assert results[0]["result"]["content"] == "CONTENT"
    assert results[0]["result"]["filename"] == "smiles_structure.pdb"
    mock_structure.assert_called_once_with("CCO", "pdb")


@patch("server.agents.smiles_tool.smiles_to_structure")
def test_process_tool_calls_smiles_error_returns_error_result(mock_structure):
    mock_structure.side_effect = ValueError("Invalid SMILES string")
    tool_calls = [
        {
            "function": {
                "name": "show_smiles_in_viewer",
                "arguments": json.dumps({"smiles": "invalid", "format": "pdb"}),
            }
        },
    ]
    results = process_tool_calls(tool_calls)
    assert len(results) == 1
    assert results[0]["name"] == "show_smiles_in_viewer"
    assert "error" in results[0]["result"]
    assert "Invalid SMILES" in results[0]["result"]["error"]
