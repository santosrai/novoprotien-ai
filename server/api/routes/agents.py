"""Agent routing and invocation API endpoints."""

import asyncio as _asyncio
import json as _json
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

try:
    from ...agents.registry import agents, list_agents
    from ...agents.runner import run_react_agent, run_supervisor_stream
    from ...infrastructure.utils import log_line, spell_fix
    from ...infrastructure.langsmith_config import langsmith_context
    from ...api.middleware.auth import get_current_user
    from ...api.limiter import limiter, DEBUG_API
except ImportError:
    from agents.registry import agents, list_agents
    from agents.runner import run_react_agent, run_supervisor_stream
    from infrastructure.utils import log_line, spell_fix
    from infrastructure.langsmith_config import langsmith_context
    from api.middleware.auth import get_current_user
    from api.limiter import limiter, DEBUG_API

try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):
        def noop(f):
            return f
        return noop

router = APIRouter()

# ---------------------------------------------------------------------------
# Abort registry: allows frontend to cancel in-progress agent streams
# ---------------------------------------------------------------------------

_abort_events: dict[str, _asyncio.Event] = {}


def get_abort_event(session_id: str) -> _asyncio.Event:
    """Get or create an abort event for a session."""
    if session_id not in _abort_events:
        _abort_events[session_id] = _asyncio.Event()
    return _abort_events[session_id]


def clear_abort_event(session_id: str):
    """Clean up an abort event after the stream completes."""
    _abort_events.pop(session_id, None)


# ---------------------------------------------------------------------------
# Models config (only used by /api/models)
# ---------------------------------------------------------------------------

_models_config_cache: Dict[str, Any] = None


def _load_models_config() -> Dict[str, Any]:
    """Load models configuration from JSON file."""
    global _models_config_cache

    if _models_config_cache is not None:
        return _models_config_cache

    try:
        server_dir = Path(__file__).parent.parent.parent
        config_path = server_dir / "models_config.json"

        if not config_path.exists():
            log_line("models_config_not_found", {"path": str(config_path)})
            return {"models": []}

        with open(config_path, "r", encoding="utf-8") as f:
            config = _json.load(f)

        _models_config_cache = config
        log_line("models_config_loaded", {"count": len(config.get("models", []))})
        return config

    except _json.JSONDecodeError as e:
        log_line("models_config_invalid_json", {"error": str(e)})
        return {"models": []}
    except Exception as e:
        log_line("models_config_load_error", {"error": str(e), "trace": traceback.format_exc()})
        return {"models": []}


# ---------------------------------------------------------------------------
# Helper: build run_supervisor_stream kwargs from request body
# ---------------------------------------------------------------------------

def _body_to_stream_args(body: dict, user: Dict[str, Any]) -> dict:
    """Build run_supervisor_stream kwargs from either legacy payload or LangGraph SDK payload."""
    try:
        from ...database.db import get_db
    except ImportError:
        from database.db import get_db

    raw_input = body.get("input")
    configurable = (
        (body.get("config") or {}).get("configurable")
        or (body.get("context") or {}).get("configurable")
        or {}
    )

    if isinstance(raw_input, str):
        input_text = raw_input
        history = body.get("history") or []
    elif isinstance(raw_input, dict) and isinstance(raw_input.get("messages"), list):
        messages = raw_input["messages"]
        input_text = ""
        history = []
        for m in messages:
            if not isinstance(m, dict):
                continue
            content = m.get("content") or m.get("text")
            if isinstance(content, list):
                content = next((c.get("text", "") for c in content if c.get("type") == "text"), "") or ""
            if not isinstance(content, str):
                content = str(content) if content is not None else ""
            role = (m.get("type") or m.get("role") or "").lower()
            if role in ("human", "user"):
                history.append({"type": "user", "content": content})
                input_text = content
            elif role in ("ai", "assistant"):
                history.append({"type": "ai", "content": content})
        history = history[:-1] if history and input_text else history
    else:
        input_text = str(raw_input) if raw_input else ""
        history = body.get("history") or []

    pipeline_id = body.get("pipeline_id") or configurable.get("pipeline_id")
    pipeline_data = body.get("pipeline_data") if isinstance(body.get("pipeline_data"), dict) else None
    if pipeline_id and pipeline_data is None and user:
        with get_db() as conn:
            row = conn.execute(
                "SELECT id, name, structure FROM pipelines WHERE id = ? AND user_id = ?",
                (pipeline_id, user["id"]),
            ).fetchone()
            if row:
                pipeline_data = _json.loads(row[2]) if row[2] else {}

    manual_agent_id = body.get("agentId") or configurable.get("agentId") or None

    return {
        "user_text": spell_fix(input_text) if input_text else input_text,
        "current_code": body.get("currentCode") or configurable.get("currentCode"),
        "history": body.get("history") if body.get("history") is not None else history,
        "selection": body.get("selection") or configurable.get("selection"),
        "selections": body.get("selections") or configurable.get("selections"),
        "uploaded_file_context": body.get("uploadedFile") or configurable.get("uploadedFile"),
        "structure_metadata": body.get("structureMetadata") or configurable.get("structureMetadata"),
        "pipeline_id": pipeline_id,
        "pipeline_data": pipeline_data,
        "model_override": body.get("model") or configurable.get("model"),
        "manual_agent_id": manual_agent_id,
    }


# ---------------------------------------------------------------------------
# Traced agent invocation
# ---------------------------------------------------------------------------

@traceable(name="AgentRoute", run_type="chain")
async def _invoke_route_and_agent(
    *,
    input_text: str,
    body: Dict[str, Any],
    manual_agent_id: Optional[str],
    pipeline_id: Optional[str],
    pipeline_data: Optional[Dict[str, Any]],
    model_override: Optional[str],
    user: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    res = await run_react_agent(
        user_text=input_text,
        current_code=body.get("currentCode"),
        history=body.get("history"),
        selection=body.get("selection"),
        selections=body.get("selections"),
        current_structure_origin=body.get("currentStructureOrigin"),
        uploaded_file_context=body.get("uploadedFile"),
        structure_metadata=body.get("structureMetadata"),
        pipeline_id=pipeline_id,
        pipeline_data=pipeline_data,
        model_override=model_override,
    )
    reason = "tool_calling"
    if manual_agent_id and manual_agent_id in agents:
        reason = f"Manual: {agents[manual_agent_id].get('name', manual_agent_id)}"
    return {"agentId": "react", **res, "reason": reason}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/api/agents")
def get_agents(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return {"agents": list_agents()}


@router.get("/api/models")
@limiter.limit("120/minute")
async def get_models(request: Request, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Get available models from configuration file."""
    config = _load_models_config()
    models = config.get("models", [])
    models.sort(key=lambda x: (x.get("provider", "Other"), x.get("name", "")))
    log_line("models_returned", {"count": len(models)})
    return {"models": models}


@router.post("/api/agents/invoke")
@limiter.limit("30/minute")
async def invoke(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        from ...agents.runner import run_agent  # type: ignore
    except ImportError:
        try:
            from agents.runner import run_agent  # type: ignore
        except ImportError:
            run_agent = None

    try:
        body = await request.json()
        agent_id = body.get("agentId")
        input_text = body.get("input")
        if not agent_id or agent_id not in agents or not isinstance(input_text, str):
            return {"error": "invalid_input"}
        res = await run_agent(
            agent=agents[agent_id],
            user_text=input_text,
            current_code=body.get("currentCode"),
            history=body.get("history"),
            selection=body.get("selection"),
            selections=body.get("selections"),
        )
        return {"agentId": agent_id, **res}
    except Exception as e:
        log_line("agent_invoke_failed", {"error": str(e), "trace": traceback.format_exc()})
        content = {"error": "agent_invoke_failed"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)


@router.post("/api/agents/route")
@limiter.limit("60/minute")
async def route(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        from ...infrastructure.utils import summarize_json
        from ...database.db import get_db
    except ImportError:
        from infrastructure.utils import summarize_json
        from database.db import get_db

    try:
        body = await request.json()
        input_text = body.get("input")
        if not isinstance(input_text, str):
            return {"error": "invalid_input"}
        input_text = spell_fix(input_text)

        manual_agent_id = body.get("agentId")
        model_override = body.get("model")
        pipeline_id = body.get("pipeline_id")
        pipeline_data = body.get("pipeline_data") if isinstance(body.get("pipeline_data"), dict) else None

        if pipeline_id and pipeline_data is None and user:
            try:
                with get_db() as conn:
                    row = conn.execute(
                        "SELECT * FROM pipelines WHERE id = ? AND user_id = ?",
                        (pipeline_id, user["id"]),
                    ).fetchone()
                    if row:
                        node_rows = conn.execute(
                            "SELECT * FROM pipeline_nodes WHERE pipeline_id = ? ORDER BY created_at",
                            (pipeline_id,),
                        ).fetchall()
                        edge_rows = conn.execute(
                            "SELECT * FROM pipeline_edges WHERE pipeline_id = ?",
                            (pipeline_id,),
                        ).fetchall()
                        nodes = []
                        for n in node_rows:
                            nd = dict(n)
                            nodes.append({
                                "id": nd["id"],
                                "type": nd["type"],
                                "label": nd["label"],
                                "config": _json.loads(nd["config"]) if nd.get("config") else {},
                                "inputs": _json.loads(nd["inputs"]) if nd.get("inputs") else {},
                                "status": nd["status"],
                                "result_metadata": _json.loads(nd["result_metadata"]) if nd.get("result_metadata") else None,
                                "error": nd.get("error"),
                                "position": {"x": nd.get("position_x", 0), "y": nd.get("position_y", 0)},
                            })
                        edges = [
                            {"source": dict(e)["source_node_id"], "target": dict(e)["target_node_id"]}
                            for e in edge_rows
                        ]
                        pipeline_data = {
                            "id": row["id"],
                            "name": row["name"],
                            "description": row["description"],
                            "status": row["status"],
                            "created_at": row["created_at"],
                            "updated_at": row["updated_at"],
                            "nodes": nodes,
                            "edges": edges,
                        }

                        exec_rows = conn.execute(
                            """SELECT id, status, trigger_type, started_at, completed_at,
                                      total_duration_ms, error_summary
                               FROM pipeline_executions
                               WHERE pipeline_id = ?
                               ORDER BY started_at DESC
                               LIMIT 5""",
                            (pipeline_id,),
                        ).fetchall()
                        pipeline_data["recent_executions"] = [
                            {
                                "id": dict(r)["id"],
                                "status": dict(r)["status"],
                                "trigger_type": dict(r)["trigger_type"],
                                "started_at": dict(r)["started_at"],
                                "completed_at": dict(r)["completed_at"],
                                "total_duration_ms": dict(r)["total_duration_ms"],
                                "error_summary": dict(r)["error_summary"],
                            }
                            for r in exec_rows
                        ]

                        latest_exec_id = dict(exec_rows[0])["id"] if exec_rows else None
                        if latest_exec_id:
                            ne_rows = conn.execute(
                                """SELECT node_id, node_label, node_type, status,
                                          duration_ms, error, input_data, output_data,
                                          execution_order
                                   FROM pipeline_node_executions
                                   WHERE execution_id = ?
                                   ORDER BY execution_order""",
                                (latest_exec_id,),
                            ).fetchall()
                            pipeline_data["latest_node_executions"] = [
                                {
                                    "node_id": dict(r)["node_id"],
                                    "node_label": dict(r)["node_label"],
                                    "node_type": dict(r)["node_type"],
                                    "status": dict(r)["status"],
                                    "duration_ms": dict(r)["duration_ms"],
                                    "error": dict(r)["error"],
                                    "input_summary": summarize_json(dict(r)["input_data"]),
                                    "output_summary": summarize_json(dict(r)["output_data"]),
                                    "execution_order": dict(r)["execution_order"],
                                }
                                for r in ne_rows
                            ]
                        else:
                            pipeline_data["latest_node_executions"] = []

                        file_rows = conn.execute(
                            """SELECT node_id, filename, role, file_type, file_url
                               FROM pipeline_node_files
                               WHERE pipeline_id = ?
                               ORDER BY created_at DESC""",
                            (pipeline_id,),
                        ).fetchall()
                        pipeline_data["node_files"] = [
                            {
                                "node_id": dict(r)["node_id"],
                                "filename": dict(r)["filename"],
                                "role": dict(r)["role"],
                                "file_type": dict(r)["file_type"],
                                "file_url": dict(r)["file_url"],
                            }
                            for r in file_rows
                        ]

                        log_line("agent_route:pipeline_fetched", {
                            "pipeline_id": pipeline_id,
                            "pipeline_name": pipeline_data.get("name"),
                            "node_count": len(nodes),
                            "execution_count": len(pipeline_data["recent_executions"]),
                            "node_execution_count": len(pipeline_data["latest_node_executions"]),
                            "file_count": len(pipeline_data["node_files"]),
                            "has_user": True,
                        })
                    else:
                        log_line("agent_route:pipeline_not_found", {
                            "pipeline_id": pipeline_id,
                            "user_id": user["id"],
                        })
            except Exception as e:
                log_line("agent_route:pipeline_fetch_error", {
                    "pipeline_id": pipeline_id,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                })

        log_line("agent_route_input", {
            "input": input_text,
            "input_length": len(input_text),
            "has_selection": bool(body.get("selection")),
            "has_code": bool(body.get("currentCode")),
            "has_pipeline_id": bool(pipeline_id),
            "manual_agent": manual_agent_id,
            "model_override": model_override,
        })

        if manual_agent_id and manual_agent_id not in agents:
            return {"error": "invalid_agent_id", "agentId": manual_agent_id}

        langsmith_cfg = body.get("langsmith")
        with langsmith_context(langsmith_cfg):
            result = await _invoke_route_and_agent(
                input_text=input_text,
                body=body,
                manual_agent_id=manual_agent_id,
                pipeline_id=pipeline_id,
                pipeline_data=pipeline_data,
                model_override=model_override,
                user=user,
            )

        if "error" in result and result.get("error") == "router_no_decision":
            return result

        agent_id = result.get("agentId")
        log_line("agent_route_result", {
            "input": input_text,
            "agentId": agent_id,
            "reason": result.get("reason"),
            "is_alphafold": agent_id == "alphafold-agent",
            "manual_override": bool(manual_agent_id),
        })
        tool_results = result.get("toolResults") or []
        log_line("agent_completed", {
            "agentId": agent_id,
            "response_type": result.get("type"),
            "has_text": "text" in result,
            "has_code": "code" in result,
            "text_length": len(result.get("text", "")) if result.get("text") else 0,
            "tools_used": bool(tool_results),
            "tool_names": [t.get("name") for t in tool_results if isinstance(t, dict)] if tool_results else [],
        })

        return result
    except Exception as e:
        log_line("agent_route_failed", {"error": str(e), "trace": traceback.format_exc()})
        content = {"error": "agent_route_failed"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)


@router.post("/api/agents/route/stream")
@limiter.limit("60/minute")
async def route_stream(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    """Stream agent execution via LangGraph. Yields NDJSON events."""

    async def _generate():
        try:
            body = await request.json()
        except Exception:
            yield _json.dumps({"type": "error", "data": {"error": "invalid_json"}}) + "\n"
            return
        input_text = body.get("input")
        if not isinstance(input_text, str):
            yield _json.dumps({"type": "error", "data": {"error": "invalid_input"}}) + "\n"
            return
        input_text = spell_fix(input_text)
        manual_agent_id = body.get("agentId")
        model_override = body.get("model")
        pipeline_id = body.get("pipeline_id")
        pipeline_data = body.get("pipeline_data") if isinstance(body.get("pipeline_data"), dict) else None
        if pipeline_id and pipeline_data is None and user:
            try:
                from ...database.db import get_db
            except ImportError:
                from database.db import get_db
            with get_db() as conn:
                row = conn.execute(
                    "SELECT id, name, structure FROM pipelines WHERE id = ? AND user_id = ?",
                    (pipeline_id, user["id"]),
                ).fetchone()
                if row:
                    pipeline_data = _json.loads(row[2]) if row[2] else {}
        try:
            async for event in run_supervisor_stream(
                user_text=input_text,
                current_code=body.get("currentCode"),
                history=body.get("history"),
                selection=body.get("selection"),
                selections=body.get("selections"),
                uploaded_file_context=body.get("uploadedFile"),
                structure_metadata=body.get("structureMetadata"),
                pipeline_id=pipeline_id,
                pipeline_data=pipeline_data,
                model_override=model_override,
                manual_agent_id=manual_agent_id,
            ):
                yield _json.dumps(event) + "\n"
        except Exception as e:
            log_line("agent_route_stream_failed", {"error": str(e), "trace": traceback.format_exc()})
            yield _json.dumps({"type": "error", "data": {"error": str(e)}}) + "\n"

    return StreamingResponse(
        _generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/agents/abort")
async def abort_agent_stream(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    """Signal the backend to abort an in-progress agent stream."""
    body = await request.json()
    session_id = body.get("session_id", "")
    if not session_id:
        return {"status": "error", "message": "session_id required"}
    event = _abort_events.get(session_id)
    if event:
        event.set()
        print(f"[Abort] Set abort flag for session {session_id}", flush=True)
        return {"status": "aborted"}
    print(f"[Abort] No active stream for session {session_id}", flush=True)
    return {"status": "no_active_stream"}


@router.post("/api/agents/route/stream/sse")
@limiter.limit("60/minute")
async def route_stream_sse(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    """Stream agent execution as SSE for LangGraph SDK (FetchStreamTransport).

    IMPORTANT: Request body is read BEFORE creating StreamingResponse because
    Starlette does not support reading request.json() inside a generator — it hangs.
    """
    import uuid as _uuid

    def _log(msg: str):
        print(msg, flush=True)

    try:
        body = await request.json()
    except Exception:
        _log("[SSE] ERROR: invalid JSON body")

        async def _err():
            yield f"event: error\ndata: {_json.dumps({'message': 'invalid_json'})}\n\n"

        return StreamingResponse(
            _err(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    _log(f"[SSE] body keys: {list(body.keys())}, input type: {type(body.get('input'))}")

    try:
        stream_args = _body_to_stream_args(body, user)
    except Exception as e:
        _log(f"[SSE] ERROR parsing body: {e}")

        async def _err():
            yield f"event: error\ndata: {_json.dumps({'message': str(e)})}\n\n"

        return StreamingResponse(
            _err(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    _log(f"[SSE] user_text: {repr(stream_args['user_text'][:80] if stream_args.get('user_text') else None)}")

    if not stream_args["user_text"]:
        _log("[SSE] ERROR: empty user_text → invalid_input")

        async def _err():
            yield f"event: error\ndata: {_json.dumps({'message': 'invalid_input'})}\n\n"

        return StreamingResponse(
            _err(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    configurable = body.get("config", {}).get("configurable", {})
    session_id = configurable.get("session_id", "")
    abort_event = get_abort_event(session_id) if session_id else _asyncio.Event()

    async def _generate():
        try:
            collected_content: list = []
            event_count = 0
            ai_msg_id = str(_uuid.uuid4())
            _log(f"[SSE] Starting supervisor stream, ai_msg_id={ai_msg_id}, session_id={session_id}")
            async for event in run_supervisor_stream(**stream_args, abort_event=abort_event):
                if abort_event.is_set():
                    _log(f"[SSE] Abort requested for session {session_id}, stopping stream")
                    break
                if await request.is_disconnected():
                    _log("[SSE] Client disconnected, stopping stream")
                    break
                event_count += 1
                etype = event.get("type")
                _log(f"[SSE] event #{event_count}: type={etype}")
                if etype == "routing":
                    payload = _json.dumps(event.get("data") or {})
                    yield f"event: metadata\ndata: {payload}\n\n"
                elif etype == "tool_call":
                    payload = _json.dumps({"tool": (event.get("data") or {}).get("name")})
                    yield f"event: metadata\ndata: {payload}\n\n"
                elif etype == "content":
                    text = (event.get("data") or {}).get("text") or ""
                    if isinstance(text, str) and text:
                        collected_content.append(text)
                        serialized = {"type": "AIMessageChunk", "id": ai_msg_id, "content": text}
                        metadata = {"langgraph_node": "agent"}
                        payload = _json.dumps([serialized, metadata])
                        yield f"event: messages\ndata: {payload}\n\n"
                elif etype == "complete":
                    data = event.get("data") or {}
                    full_text = data.get("text") or "".join(collected_content) or data.get("code") or ""
                    _log(f"[SSE] complete: full_text len={len(full_text)}, agentId={data.get('agentId')}, tools={data.get('toolsInvoked')}")
                    history = stream_args.get("history") or []
                    lc_messages: list = []
                    for h in history:
                        role = h.get("type", "user")
                        lc_messages.append({
                            "type": "human" if role == "user" else "ai",
                            "id": str(_uuid.uuid4()),
                            "content": h.get("content") or "",
                        })
                    lc_messages.append({"type": "ai", "id": ai_msg_id, "content": full_text})
                    app_result = {
                        k: data.get(k)
                        for k in ("agentId", "text", "code", "reason", "type", "thinkingProcess", "toolsInvoked", "toolResults", "uniprotSearchResult", "uniprotDetailResult", "tokenUsage", "alignmentResult", "af2bindResult")
                        if data.get(k) is not None
                    }
                    values_payload = _json.dumps({"messages": lc_messages, "appResult": app_result})
                    _log(f"[SSE] yielding values event, messages count: {len(lc_messages)}")
                    yield f"event: values\ndata: {values_payload}\n\n"
                elif etype == "error":
                    err = (event.get("data") or {}).get("error") or "Unknown error"
                    _log(f"[SSE] yielding error event: {err}")
                    error_text = f"⚠️ {err}"
                    err_serialized = {"type": "AIMessageChunk", "id": ai_msg_id, "content": error_text}
                    err_metadata = {"langgraph_node": "agent"}
                    yield f"event: messages\ndata: {_json.dumps([err_serialized, err_metadata])}\n\n"
                    history = stream_args.get("history") or []
                    lc_messages_err: list = []
                    for h in history:
                        role = h.get("type", "user")
                        lc_messages_err.append({
                            "type": "human" if role == "user" else "ai",
                            "id": str(_uuid.uuid4()),
                            "content": h.get("content") or "",
                        })
                    lc_messages_err.append({"type": "ai", "id": ai_msg_id, "content": error_text})
                    err_values_payload = _json.dumps({
                        "messages": lc_messages_err,
                        "appResult": {"text": error_text},
                    })
                    _log(f"[SSE] yielding values event for error, messages count: {len(lc_messages_err)}")
                    yield f"event: values\ndata: {err_values_payload}\n\n"
            _log(f"[SSE] stream ended, total events: {event_count}, collected content len: {len(''.join(collected_content))}")
        except Exception as e:
            _log(f"[SSE] EXCEPTION: {e}")
            import traceback as _tb
            _log(f"[SSE] traceback: {_tb.format_exc()}")
            log_line("agent_route_stream_sse_failed", {"error": str(e), "trace": _tb.format_exc()})
            exc_text = f"⚠️ Something went wrong: {e}"
            exc_serialized = {"type": "AIMessageChunk", "id": ai_msg_id, "content": exc_text}
            exc_metadata = {"langgraph_node": "agent"}
            yield f"event: messages\ndata: {_json.dumps([exc_serialized, exc_metadata])}\n\n"
            history = stream_args.get("history") or []
            lc_messages_exc: list = []
            for h in history:
                role = h.get("type", "user")
                lc_messages_exc.append({
                    "type": "human" if role == "user" else "ai",
                    "id": str(_uuid.uuid4()),
                    "content": h.get("content") or "",
                })
            lc_messages_exc.append({"type": "ai", "id": ai_msg_id, "content": exc_text})
            exc_values_payload = _json.dumps({
                "messages": lc_messages_exc,
                "appResult": {"text": exc_text},
            })
            _log(f"[SSE] yielding values event for exception, messages count: {len(lc_messages_exc)}")
            yield f"event: values\ndata: {exc_values_payload}\n\n"
        finally:
            if session_id:
                clear_abort_event(session_id)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
