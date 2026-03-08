"""
Map agent graph output to app result format: {"type": "text"|"code", "text", "code"?, "toolResults"?}.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

try:
    from langchain_core.messages import AIMessage, ToolMessage
except ImportError:
    AIMessage = None
    ToolMessage = None

from ..llm.messages import langchain_to_app_text

try:
    from ...infrastructure.utils import extract_code_and_text
    from ...infrastructure.safety import violates_whitelist, ensure_clear_on_change
except ImportError:
    from infrastructure.utils import extract_code_and_text
    from infrastructure.safety import violates_whitelist, ensure_clear_on_change


def _to_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_token_usage(raw: Any) -> Optional[Dict[str, int]]:
    if not isinstance(raw, dict):
        return None
    input_tokens = _to_int(raw.get("input_tokens"))
    if input_tokens is None:
        input_tokens = _to_int(raw.get("prompt_tokens"))
    output_tokens = _to_int(raw.get("output_tokens"))
    if output_tokens is None:
        output_tokens = _to_int(raw.get("completion_tokens"))
    total_tokens = _to_int(raw.get("total_tokens"))

    if input_tokens is None and output_tokens is None and total_tokens is None:
        return None

    if input_tokens is None:
        if total_tokens is not None and output_tokens is not None:
            input_tokens = max(total_tokens - output_tokens, 0)
        else:
            input_tokens = 0
    if output_tokens is None:
        if total_tokens is not None and input_tokens is not None:
            output_tokens = max(total_tokens - input_tokens, 0)
        else:
            output_tokens = 0
    if total_tokens is None:
        total_tokens = input_tokens + output_tokens

    return {
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "totalTokens": total_tokens,
    }


def _extract_token_usage(messages: List[Any]) -> Optional[Dict[str, int]]:
    if AIMessage is None:
        return None
    for m in reversed(messages):
        if not isinstance(m, AIMessage):
            continue

        usage_metadata = getattr(m, "usage_metadata", None)
        normalized = _normalize_token_usage(usage_metadata)
        if normalized:
            return normalized

        response_metadata = getattr(m, "response_metadata", None)
        if isinstance(response_metadata, dict):
            normalized = _normalize_token_usage(response_metadata.get("token_usage"))
            if normalized:
                return normalized
    return None


def react_state_to_app_result(final_state: Dict[str, Any]) -> Dict[str, Any]:
    """Convert ReAct graph final state to app result. Handles tool_results and action JSON for frontend."""
    messages = final_state.get("messages") or []
    text, tool_results_from_lc = langchain_to_app_text(messages)
    tool_results: List[Dict[str, Any]] = list(tool_results_from_lc) if tool_results_from_lc else []
    token_usage = _extract_token_usage(messages)

    # Collect results from ToolMessages (action dialogs, search_uniprot); skip show_smiles (already in tool_results_from_lc)
    existing_names = {t["name"] for t in tool_results}
    action_text: Optional[str] = None
    if ToolMessage is not None:
        for m in messages:
            if isinstance(m, ToolMessage):
                name = getattr(m, "name", None) or "tool"
                if name in existing_names:
                    continue
                existing_names.add(name)
                content = m.content
                if isinstance(content, str) and content.strip().startswith("{"):
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, dict) and parsed.get("action"):
                            action_text = content  # Frontend parses this to open dialogs
                        tool_results.append({"name": name, "result": parsed})
                    except json.JSONDecodeError:
                        tool_results.append({"name": name, "result": {"output": content}})
                else:
                    tool_results.append({"name": name, "result": {"output": content}})

    # If a tool returned action JSON, send that as text so the frontend can parse it
    if action_text:
        text = action_text

    # Detect code in last AI content
    content_for_code = ""
    for m in reversed(messages):
        if AIMessage and isinstance(m, AIMessage) and m.content:
            content_for_code = m.content if isinstance(m.content, str) else str(m.content)
            break
    code, explanation = extract_code_and_text(content_for_code)
    if code and code.strip():
        code = ensure_clear_on_change(None, code)
        if violates_whitelist(code):
            out = {"type": "code", "code": code, "text": explanation or text}
        else:
            out = {"type": "code", "code": code, "text": explanation}
        if tool_results:
            out["toolResults"] = tool_results
        if token_usage:
            out["tokenUsage"] = token_usage
        return out

    out = {"type": "text", "text": text or ""}
    if tool_results:
        out["toolResults"] = tool_results
    if token_usage:
        out["tokenUsage"] = token_usage
    return out


def agent_output_to_app_result(
    final_state: Dict[str, Any],
    agent_kind: str,
    *,
    current_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Convert LangGraph final state to runner app result dict.

    Args:
        final_state: State returned by compiled graph .invoke(); must have "messages".
        agent_kind: "text" or "code".
        current_code: For code agents, previous code for ensure_clear_on_change.

    Returns:
        {"type": "text", "text": ..., "toolResults": ...} or
        {"type": "code", "code": ..., "text": ...}.
    """
    messages = final_state.get("messages") or []

    if agent_kind == "text":
        text, tool_results = langchain_to_app_text(messages)
        result = {"type": "text", "text": text or ""}
        if tool_results:
            result["toolResults"] = tool_results
        token_usage = _extract_token_usage(messages)
        if token_usage:
            result["tokenUsage"] = token_usage
        return result

    if agent_kind == "code":
        content = ""
        for m in reversed(messages):
            if AIMessage and isinstance(m, AIMessage) and m.content:
                content = m.content if isinstance(m.content, str) else str(m.content)
                break
        code, explanation_text = extract_code_and_text(content)
        if code and code.strip() and violates_whitelist(code):
            code = ensure_clear_on_change(current_code, code)
        else:
            code = ensure_clear_on_change(current_code, code)
        out = {"type": "code", "code": code}
        if explanation_text:
            out["text"] = explanation_text
        # Include tool results (e.g. show_smiles_in_viewer) so frontend can load PDB/SDF
        _, tool_results = langchain_to_app_text(messages)
        if tool_results:
            out["toolResults"] = tool_results
        token_usage = _extract_token_usage(messages)
        if token_usage:
            out["tokenUsage"] = token_usage
        return out

    # Fallback for unknown kind
    text, _ = langchain_to_app_text(messages)
    out = {"type": "text", "text": text or ""}
    token_usage = _extract_token_usage(messages)
    if token_usage:
        out["tokenUsage"] = token_usage
    return out
