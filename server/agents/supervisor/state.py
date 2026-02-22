"""Supervisor state definition (for reference — streaming bypasses full graph)."""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional, Sequence, TypedDict

try:
    from langchain_core.messages import BaseMessage
    from langgraph.graph.message import add_messages
except ImportError:
    BaseMessage = Any
    add_messages = None


class SupervisorState(TypedDict, total=False):
    """State shared across the supervisor routing and sub-agent execution."""

    # Core message thread
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # Routing
    active_agent: Optional[str]       # "bio_chat" | "code_builder" | "pipeline"
    routing_reason: Optional[str]
    manual_override: Optional[str]

    # Context passed from API request
    current_code: Optional[str]
    uploaded_file_context: Optional[Dict[str, Any]]
    structure_metadata: Optional[Dict[str, Any]]
    pipeline_id: Optional[str]
    pipeline_data: Optional[Dict[str, Any]]
    selection: Optional[Dict[str, Any]]
    selections: Optional[List[Dict[str, Any]]]

    # Result metadata for frontend pills
    tools_invoked: Optional[List[str]]

    # Final app result
    app_result: Optional[Dict[str, Any]]
