"""
Process OpenRouter streaming chunks into app events (thinking_step, content, complete).
Preserves thinking-step semantics; used by run_agent_stream for thinking models.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterator, List, Optional

try:
    from ...infrastructure.utils import extract_code_and_text
    from ...infrastructure.safety import violates_whitelist, ensure_clear_on_change
except ImportError:
    from infrastructure.utils import extract_code_and_text
    from infrastructure.safety import violates_whitelist, ensure_clear_on_change


def process_openrouter_stream(
    stream_gen: Iterator[Dict[str, Any]],
    parse_incremental_thinking_step: Callable[..., tuple],
    agent_kind: str,
    *,
    current_code: Optional[str] = None,
) -> Iterator[Dict[str, Any]]:
    """Process OpenRouter stream chunks and yield app events: thinking_step, content, complete.

    Args:
        stream_gen: Iterator of {"type": "reasoning"|"content", "data": str}.
        parse_incremental_thinking_step: (accumulated_reasoning, current_step) -> (completed_step, current_step).
        agent_kind: "code" or "text".
        current_code: For code agents, previous code for ensure_clear_on_change.

    Yields:
        {"type": "thinking_step", "data": {...}} | {"type": "content", "data": {"text": ...}} | {"type": "complete", "data": {...}}.
    """
    accumulated_reasoning = ""
    accumulated_content = ""
    thinking_steps: List[Dict[str, Any]] = []
    current_step: Optional[Dict[str, Any]] = None

    for chunk in stream_gen:
        if chunk.get("type") == "reasoning":
            accumulated_reasoning += chunk.get("data", "")
            completed_step, current_step = parse_incremental_thinking_step(accumulated_reasoning, current_step)
            if completed_step:
                completed_step["status"] = "completed"
                existing_idx = next((i for i, s in enumerate(thinking_steps) if s["id"] == completed_step["id"]), None)
                if existing_idx is not None:
                    thinking_steps[existing_idx] = completed_step
                else:
                    thinking_steps.append(completed_step)
                yield {"type": "thinking_step", "data": completed_step}
            if current_step:
                existing_idx = next((i for i, s in enumerate(thinking_steps) if s["id"] == current_step["id"]), None)
                if existing_idx is not None:
                    thinking_steps[existing_idx] = current_step
                else:
                    thinking_steps.append(current_step)
                yield {"type": "thinking_step", "data": current_step}
        elif chunk.get("type") == "content":
            accumulated_content += chunk.get("data", "")
            yield {"type": "content", "data": {"text": chunk.get("data", "")}}

    if current_step:
        current_step["status"] = "completed"
        current_step["content"] = current_step.get("content", "").strip()
        existing_idx = next((i for i, s in enumerate(thinking_steps) if s["id"] == current_step["id"]), None)
        if existing_idx is not None:
            thinking_steps[existing_idx] = current_step
        else:
            thinking_steps.append(current_step)
        yield {"type": "thinking_step", "data": current_step}

    if agent_kind == "code":
        code, explanation_text = extract_code_and_text(accumulated_content)
        if code and code.strip() and violates_whitelist(code):
            code = ensure_clear_on_change(current_code, code)
        else:
            code = ensure_clear_on_change(current_code, code) if code else ""
        final_result: Dict[str, Any] = {"type": "code", "code": code}
        if explanation_text:
            final_result["text"] = explanation_text
        if thinking_steps:
            final_result["thinkingProcess"] = {
                "steps": thinking_steps,
                "isComplete": True,
                "totalSteps": len(thinking_steps),
            }
        yield {"type": "complete", "data": final_result}
    else:
        final_result = {"type": "text", "text": accumulated_content.strip()}
        if thinking_steps:
            final_result["thinkingProcess"] = {
                "steps": thinking_steps,
                "isComplete": True,
                "totalSteps": len(thinking_steps),
            }
        yield {"type": "complete", "data": final_result}
