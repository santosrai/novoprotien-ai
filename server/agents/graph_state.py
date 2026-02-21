"""
Unified state schema for the LangGraph agent routing graph.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class AgentGraphState(TypedDict, total=False):
    """State for the main agent routing graph. All keys optional."""

    # Input (from API request)
    input: str
    selection: Optional[Dict[str, Any]]
    selections: Optional[List[Dict[str, Any]]]
    history: Optional[List[Dict[str, Any]]]
    currentCode: Optional[str]
    uploadedFileId: Optional[str]
    uploadedFileContext: Optional[Dict[str, Any]]
    currentStructureOrigin: Optional[Dict[str, Any]]
    structureMetadata: Optional[Dict[str, Any]]
    pipeline_id: Optional[str]
    pipeline_data: Optional[Dict[str, Any]]
    pdb_content: Optional[str]
    model_override: Optional[str]
    user_id: Optional[str]

    # Routing
    routed_agent_id: Optional[str]
    routing_reason: Optional[str]

    # LLM state (for subgraphs / future use)
    messages: Optional[List[Any]]

    # Results
    result_type: Optional[str]  # "text", "code", "action"
    result_text: Optional[str]
    result_code: Optional[str]
    result_action: Optional[str]
    tool_results: Optional[List[Dict[str, Any]]]
    thinking_process: Optional[Dict[str, Any]]

    # Agent config (populated by router)
    agent_config: Optional[Dict[str, Any]]
