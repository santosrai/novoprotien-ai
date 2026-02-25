import asyncio
import os
import traceback
import time
import json
from typing import Any, Dict, Optional
from pathlib import Path

from dotenv import load_dotenv
import httpx

# Load env as early as possible, before importing modules that read env at import-time
# Load .env from project root (one level up from server directory)
project_root = os.path.dirname(os.path.dirname(__file__))
env_path = os.path.join(project_root, '.env')

if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
    print(f"Loaded .env from: {env_path}")
else:
    print(f"Warning: .env file not found at {env_path}")

# Also load from server directory (for keys like NVCF_RUN_KEY)
server_env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(server_env_path):
    load_dotenv(server_env_path, override=True)
    print(f"Also loaded .env from: {server_env_path}")



# LangSmith tracing (must run after env load, before agent imports)
try:
    from .infrastructure.langsmith_config import setup_langsmith
    setup_langsmith()
except ImportError:
    try:
        from infrastructure.langsmith_config import setup_langsmith
        setup_langsmith()
    except Exception:
        pass
except Exception:
    pass


from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse

try:
    from langsmith import traceable, tracing_context, Client as LangSmithClient
except ImportError:
    def traceable(*args, **kwargs):
        def noop(f):
            return f
        return noop
    tracing_context = None
    LangSmithClient = None

try:
    from .agents.registry import agents, list_agents
    from .agents.router import init_router
    from .agents.runner import run_react_agent
    from .infrastructure.utils import log_line, spell_fix
    from .agents.handlers.alphafold import alphafold_handler
    from .agents.handlers.rfdiffusion import rfdiffusion_handler
    from .agents.handlers.proteinmpnn import proteinmpnn_handler
    from .agents.handlers.openfold2 import openfold2_handler
    from .agents.handlers.diffdock import diffdock_handler
    from .domain.storage.pdb_storage import save_uploaded_pdb, get_uploaded_pdb
    from .domain.storage.file_access import list_user_files, verify_file_ownership, get_file_metadata, get_user_file_path
    from .tools.smiles_converter import smiles_to_structure
    from .database.db import get_db
    from .api.middleware.auth import get_current_user, get_current_user_optional
    from .api.routes import auth, chat_sessions, chat_messages, pipelines, credits, reports, admin, three_d_canvases, attachments
except ImportError:
    # When running directly (not as module)
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    try:
        from langsmith import traceable, tracing_context, Client as LangSmithClient
    except ImportError:
        def traceable(*args, **kwargs):
            def noop(f):
                return f
            return noop
        tracing_context = None
        LangSmithClient = None
    from agents.registry import agents, list_agents
    from agents.router import init_router
    from agents.runner import run_react_agent
    from infrastructure.utils import log_line, spell_fix
    from agents.handlers.alphafold import alphafold_handler
    from agents.handlers.rfdiffusion import rfdiffusion_handler
    from agents.handlers.proteinmpnn import proteinmpnn_handler
    from agents.handlers.openfold2 import openfold2_handler
    from agents.handlers.diffdock import diffdock_handler
    from domain.storage.pdb_storage import save_uploaded_pdb, get_uploaded_pdb
    from domain.storage.file_access import list_user_files, verify_file_ownership, get_file_metadata, get_user_file_path
    from tools.smiles_converter import smiles_to_structure
    from database.db import get_db
    from api.middleware.auth import get_current_user, get_current_user_optional
    from api.routes import auth, chat_sessions, chat_messages, pipelines, credits, reports, admin, three_d_canvases, attachments

DEBUG_API = os.getenv("DEBUG_API", "0") == "1"


def _summarize_json(raw: str, max_len: int = 200) -> str:
    """Truncate a JSON string for LLM context, preserving structure hints."""
    if not raw:
        return ""
    try:
        obj = json.loads(raw) if isinstance(raw, str) else raw
        compact = json.dumps(obj, separators=(",", ":"))
    except (json.JSONDecodeError, TypeError):
        compact = str(raw)
    if len(compact) <= max_len:
        return compact
    return compact[:max_len] + "…"


def _langsmith_context(langsmith_config: Optional[Dict[str, Any]]):
    """
    Return a context manager for LangSmith tracing based on user settings.
    - enabled=False: explicitly disable tracing
    - enabled=True + apiKey: use user's LangSmith client
    - enabled=True, no apiKey: use env (no-op context, default behavior)
    - no config: use env (no-op context)
    """
    if tracing_context is None:
        from contextlib import nullcontext
        return nullcontext()

    cfg = langsmith_config or {}
    enabled = cfg.get("enabled", True)

    if enabled is False:
        return tracing_context(enabled=False)

    api_key = (cfg.get("apiKey") or "").strip()
    if api_key and LangSmithClient:
        project = cfg.get("project") or "novoprotein-agent"
        client = LangSmithClient(
            api_key=api_key,
            api_url="https://api.smith.langchain.com",
        )
        return tracing_context(client=client, project_name=project)

    from contextlib import nullcontext
    return nullcontext()


def _build_initial_state(
    *,
    input_text: str,
    body: Dict[str, Any],
    manual_agent_id: Optional[str],
    pipeline_id: Optional[str],
    pipeline_data: Optional[Dict[str, Any]],
    model_override: Optional[str],
    user: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build LangGraph initial state from request."""
    uploaded = body.get("uploadedFile") or {}
    state = {
        "input": input_text,
        "selection": body.get("selection"),
        "selections": body.get("selections"),
        "history": body.get("history"),
        "currentCode": body.get("currentCode"),
        "uploadedFileId": uploaded.get("file_id"),
        "uploadedFileContext": body.get("uploadedFile"),
        "currentStructureOrigin": body.get("currentStructureOrigin"),
        "structureMetadata": body.get("structureMetadata"),
        "pipeline_id": pipeline_id,
        "pipeline_data": pipeline_data,
        "model_override": model_override,
        "user_id": user.get("id") if user else None,
        "pdb_content": body.get("pdb_content"),
    }
    if manual_agent_id and manual_agent_id in agents:
        state["routed_agent_id"] = manual_agent_id
        state["agent_config"] = agents[manual_agent_id]
        state["routing_reason"] = f"Manually selected: {agents[manual_agent_id].get('name', manual_agent_id)}"
    return state


def _final_state_to_response(final_state: Dict[str, Any]) -> Dict[str, Any]:
    """Map graph final state to API response format."""
    out = {
        "agentId": final_state.get("routed_agent_id"),
        "reason": final_state.get("routing_reason"),
        "type": final_state.get("result_type", "text"),
        "text": final_state.get("result_text"),
        "code": final_state.get("result_code"),
        "toolResults": final_state.get("tool_results"),
        "thinkingProcess": final_state.get("thinking_process"),
    }
    if final_state.get("result_type") == "error":
        out["error"] = final_state.get("result_text") or final_state.get("error") or "Agent execution failed"
    return out


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
    """ReAct agent: LLM + tool calling. No keyword routing; tools are triggered by the model from descriptions."""
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


def _rate_limit_key(request: Request) -> str:
    """In debug mode, use unique key per request to avoid localhost rate limit exhaustion."""
    if DEBUG_API:
        return f"dev-{id(request)}"
    return get_remote_address(request)


def _parse_cors_origins() -> list[str]:
    """Load CORS origins with a safe default and no wildcard+credentials combination."""
    configured = os.getenv("APP_ORIGIN", "").strip()
    if not configured:
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    if "*" in origins:
        filtered = [origin for origin in origins if origin != "*"]
        log_line(
            "cors_config_warning",
            {"message": "Wildcard APP_ORIGIN is not allowed with credentials; ignoring '*'"}
        )
        return filtered or ["http://localhost:5173", "http://127.0.0.1:5173"]

    return origins


app = FastAPI()
limiter = Limiter(key_func=_rate_limit_key)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

allowed_origins = _parse_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_router(list(agents.values()))
    
    # Suppress harmless Windows asyncio connection reset errors
    # These occur when clients close connections abruptly (browser refresh, tab close, etc.)
    import asyncio
    import logging
    import sys
    
    # Configure logging to filter out Windows connection reset errors
    class ConnectionResetFilter(logging.Filter):
        """Filter out harmless Windows connection reset errors."""
        def filter(self, record):
            # Suppress ConnectionResetError messages on Windows
            if sys.platform == 'win32':
                msg = record.getMessage()
                if 'ConnectionResetError' in msg or 'WinError 10054' in msg:
                    if '_call_connection_lost' in msg or '_ProactorBasePipeTransport' in msg:
                        return False  # Suppress this log
            return True
    
    # Add filter to asyncio logger
    asyncio_logger = logging.getLogger('asyncio')
    asyncio_logger.addFilter(ConnectionResetFilter())
    
    def handle_exception(loop, context):
        """Handle asyncio exceptions, suppressing harmless connection reset errors on Windows."""
        exception = context.get('exception')
        # Suppress Windows connection reset errors (WinError 10054)
        # These are harmless and occur when clients close connections abruptly
        if isinstance(exception, ConnectionResetError):
            # Check if it's the specific Windows error code
            if hasattr(exception, 'winerror') and exception.winerror == 10054:
                # Suppress this specific error - it's harmless
                return
            # Also suppress generic ConnectionResetError on Windows
            if sys.platform == 'win32':
                return
        # Log other exceptions normally
        if loop.default_exception_handler:
            loop.default_exception_handler(context)
        else:
            # Fallback: log to Python logger
            logging.error(f"Unhandled exception in event loop: {context}")
    
    # Set custom exception handler for the event loop
    try:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(handle_exception)
    except RuntimeError:
        # No running loop yet, set it when we get one
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.set_exception_handler(handle_exception)
        except Exception:
            # If we can't set the handler, continue anyway
            pass

# Register API routers
app.include_router(auth.router)
app.include_router(chat_sessions.router)
app.include_router(chat_messages.router)
app.include_router(pipelines.router)
app.include_router(credits.router)
app.include_router(reports.router)
app.include_router(admin.router)
app.include_router(three_d_canvases.router)
app.include_router(three_d_canvases.user_router)
app.include_router(attachments.router)


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {"ok": True}


@app.post("/api/logs/error")
@limiter.limit("100/minute")
async def log_error(request: Request, user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Accept error logs from frontend (auth optional - capture errors during login/session issues)"""
    try:
        body = await request.json()
        log_line("frontend_error", body)
        return {"status": "logged"}
    except Exception as e:
        log_line("error_logging_failed", {"error": str(e), "trace": traceback.format_exc()})
        return JSONResponse(status_code=500, content={"error": "logging_failed"})


@app.exception_handler(RateLimitExceeded)
def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"error": "rate_limited", "detail": str(exc)})


@app.get("/api/agents")
def get_agents(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return {"agents": list_agents()}


# Cache for models config
_models_config_cache: Dict[str, Any] = None


def _load_models_config() -> Dict[str, Any]:
    """Load models configuration from JSON file."""
    global _models_config_cache
    
    if _models_config_cache is not None:
        return _models_config_cache
    
    try:
        # Get the server directory path
        server_dir = Path(__file__).parent
        config_path = server_dir / "models_config.json"
        
        if not config_path.exists():
            log_line("models_config_not_found", {"path": str(config_path)})
            return {"models": []}
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        _models_config_cache = config
        log_line("models_config_loaded", {"count": len(config.get("models", []))})
        return config
        
    except json.JSONDecodeError as e:
        log_line("models_config_invalid_json", {"error": str(e)})
        return {"models": []}
    except Exception as e:
        log_line("models_config_load_error", {"error": str(e), "trace": traceback.format_exc()})
        return {"models": []}


@app.get("/api/models")
@limiter.limit("120/minute")  # Read-only config; allow more for multi-tab/navigation
async def get_models(request: Request, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Get available models from configuration file."""
    config = _load_models_config()
    models = config.get("models", [])
    
    # Sort by provider, then by name
    models.sort(key=lambda x: (x.get("provider", "Other"), x.get("name", "")))
    
    log_line("models_returned", {"count": len(models)})
    return {"models": models}


@app.post("/api/agents/invoke")
@limiter.limit("30/minute")
async def invoke(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
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


@app.post("/api/agents/route")
@limiter.limit("60/minute")
async def route(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        body = await request.json()
        input_text = body.get("input")
        if not isinstance(input_text, str):
            return {"error": "invalid_input"}
        input_text = spell_fix(input_text)

        # Check for manual agent override
        manual_agent_id = body.get("agentId")
        model_override = body.get("model")
        pipeline_id = body.get("pipeline_id")  # Extract pipeline_id early for router
        # Use pipeline_data from body when provided (e.g. draft from frontend); else fetch by pipeline_id
        pipeline_data = body.get("pipeline_data") if isinstance(body.get("pipeline_data"), dict) else None

        # Fetch pipeline data from DB only if not already provided and user is authenticated
        if pipeline_id and pipeline_data is None and user:
            try:
                from .database.db import get_db
                import json
                with get_db() as conn:
                    row = conn.execute(
                        "SELECT * FROM pipelines WHERE id = ? AND user_id = ?",
                        (pipeline_id, user["id"]),
                    ).fetchone()
                    if row:
                        # Assemble pipeline from normalized tables
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
                                "config": json.loads(nd["config"]) if nd.get("config") else {},
                                "inputs": json.loads(nd["inputs"]) if nd.get("inputs") else {},
                                "status": nd["status"],
                                "result_metadata": json.loads(nd["result_metadata"]) if nd.get("result_metadata") else None,
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

                        # --- Fetch execution history & file references ---
                        # Last 5 pipeline executions
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

                        # Per-node details from the latest execution
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
                                    "input_summary": _summarize_json(dict(r)["input_data"]),
                                    "output_summary": _summarize_json(dict(r)["output_data"]),
                                    "execution_order": dict(r)["execution_order"],
                                }
                                for r in ne_rows
                            ]
                        else:
                            pipeline_data["latest_node_executions"] = []

                        # File references for this pipeline
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
                # Continue without pipeline data if fetch fails
        
        # Log the input for debugging
        log_line("agent_route_input", {
            "input": input_text,
            "input_length": len(input_text),
            "has_selection": bool(body.get("selection")),
            "has_code": bool(body.get("currentCode")),
            "has_pipeline_id": bool(pipeline_id),
            "manual_agent": manual_agent_id,
            "model_override": model_override
        })
        
        # If agentId is provided, validate before traced invocation
        if manual_agent_id and manual_agent_id not in agents:
            return {"error": "invalid_agent_id", "agentId": manual_agent_id}

        langsmith_config = body.get("langsmith")
        with _langsmith_context(langsmith_config):
            # LangSmith-traced: router → run_agent
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
            "manual_override": bool(manual_agent_id)
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


@app.post("/api/agents/route/stream")
@limiter.limit("60/minute")
async def route_stream(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    """Stream agent execution via LangGraph. Yields SSE events: node updates, then final complete event."""
    import json as _json

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
            with get_db() as conn:
                row = conn.execute(
                    "SELECT id, name, structure FROM pipelines WHERE id = ? AND user_id = ?",
                    (pipeline_id, user["id"]),
                ).fetchone()
                if row:
                    pipeline_data = _json.loads(row[2]) if row[2] else {}
        try:
            from .agents.runner import run_supervisor_stream
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
                # NDJSON: one JSON object per line for frontend streamAgentRoute()
                yield _json.dumps(event) + "\n"
        except Exception as e:
            log_line("agent_route_stream_failed", {"error": str(e), "trace": traceback.format_exc()})
            yield _json.dumps({"type": "error", "data": {"error": str(e)}}) + "\n"

    return StreamingResponse(
        _generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _body_to_stream_args(body: dict, user: Dict[str, Any]) -> dict:
    """Build run_supervisor_stream kwargs from either legacy payload or LangGraph SDK payload.
    SDK sends: { input: ..., config: { configurable: { ... } } }
    Legacy sends: { input: ..., context: { configurable: { ... } } } or flat keys."""
    import json as _json
    raw_input = body.get("input")
    # SDK (FetchStreamTransport) puts configurable inside "config"; legacy used "context"
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
        history = history[:-1] if history and input_text else history  # exclude current user message
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

    # Extract manual agent selection (null/absent = auto-route via supervisor)
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


@app.post("/api/agents/route/stream/sse")
@limiter.limit("60/minute")
async def route_stream_sse(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    """Stream agent execution as SSE for LangGraph SDK (FetchStreamTransport).
    Accepts SDK-style body: { input: { messages: [...] }, config: { configurable: {...} } }.

    IMPORTANT: Request body is read BEFORE creating StreamingResponse because
    Starlette does not support reading request.json() inside a generator — it hangs.
    """
    import json as _json

    def _log(msg: str):
        print(msg, flush=True)

    # --- Read and parse request body BEFORE creating the streaming generator ---
    try:
        body = await request.json()
    except Exception:
        _log("[SSE] ERROR: invalid JSON body")
        async def _err():
            yield f"event: error\ndata: {_json.dumps({'message': 'invalid_json'})}\n\n"
        return StreamingResponse(_err(), media_type="text/event-stream",
                                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    _log(f"[SSE] body keys: {list(body.keys())}, input type: {type(body.get('input'))}")

    try:
        stream_args = _body_to_stream_args(body, user)
    except Exception as e:
        _log(f"[SSE] ERROR parsing body: {e}")
        async def _err():
            yield f"event: error\ndata: {_json.dumps({'message': str(e)})}\n\n"
        return StreamingResponse(_err(), media_type="text/event-stream",
                                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    _log(f"[SSE] user_text: {repr(stream_args['user_text'][:80] if stream_args.get('user_text') else None)}")

    if not stream_args["user_text"]:
        _log("[SSE] ERROR: empty user_text → invalid_input")
        async def _err():
            yield f"event: error\ndata: {_json.dumps({'message': 'invalid_input'})}\n\n"
        return StreamingResponse(_err(), media_type="text/event-stream",
                                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # --- Now create the streaming generator with pre-parsed data ---
    async def _generate():
        try:
            import uuid as _uuid
            try:
                from .agents.runner import run_supervisor_stream
            except ImportError:
                from agents.runner import run_supervisor_stream

            collected_content: list = []
            event_count = 0
            # Stable message ID so SDK MessageTupleManager concatenates all chunks
            ai_msg_id = str(_uuid.uuid4())
            _log(f"[SSE] Starting supervisor stream, ai_msg_id={ai_msg_id}")
            async for event in run_supervisor_stream(**stream_args):
                event_count += 1
                etype = event.get("type")
                _log(f"[SSE] event #{event_count}: type={etype}")
                if etype == "routing":
                    # New: tell frontend which agent was selected (agent pill)
                    payload = _json.dumps(event.get("data") or {})
                    yield f"event: metadata\ndata: {payload}\n\n"
                elif etype == "tool_call":
                    # New: tell frontend which tool was invoked (tool pill)
                    payload = _json.dumps({"tool": (event.get("data") or {}).get("name")})
                    yield f"event: metadata\ndata: {payload}\n\n"
                elif etype == "content":
                    text = (event.get("data") or {}).get("text") or ""
                    if isinstance(text, str) and text:
                        collected_content.append(text)
                        # SDK StreamManager expects "messages" event with [serialized, metadata]
                        # serialized MUST have "id" so MessageTupleManager can track/concat chunks
                        serialized = {"type": "AIMessageChunk", "id": ai_msg_id, "content": text}
                        metadata = {"langgraph_node": "agent"}
                        payload = _json.dumps([serialized, metadata])
                        yield f"event: messages\ndata: {payload}\n\n"
                elif etype == "complete":
                    data = event.get("data") or {}
                    full_text = data.get("text") or "".join(collected_content) or data.get("code") or ""
                    _log(f"[SSE] complete: full_text len={len(full_text)}, agentId={data.get('agentId')}, tools={data.get('toolsInvoked')}")
                    # Build history messages with IDs for the SDK values event
                    history = stream_args.get("history") or []
                    lc_messages: list = []
                    for i, h in enumerate(history):
                        role = h.get("type", "user")
                        lc_messages.append({
                            "type": "human" if role == "user" else "ai",
                            "id": str(_uuid.uuid4()),
                            "content": h.get("content") or "",
                        })
                    # Final AI message uses the same ID as the streamed chunks
                    lc_messages.append({"type": "ai", "id": ai_msg_id, "content": full_text})
                    # Include app result so frontend can handle agentId, code, actions, toolsInvoked, etc.
                    app_result = {k: data.get(k) for k in ("agentId", "text", "code", "reason", "type", "thinkingProcess", "toolsInvoked") if data.get(k) is not None}
                    values_payload = _json.dumps({"messages": lc_messages, "appResult": app_result})
                    _log(f"[SSE] yielding values event, messages count: {len(lc_messages)}")
                    yield f"event: values\ndata: {values_payload}\n\n"
                elif etype == "error":
                    err = (event.get("data") or {}).get("error") or "Unknown error"
                    _log(f"[SSE] yielding error event: {err}")
                    yield f"event: error\ndata: {_json.dumps({'message': str(err)})}\n\n"
            _log(f"[SSE] stream ended, total events: {event_count}, collected content len: {len(''.join(collected_content))}")
        except Exception as e:
            _log(f"[SSE] EXCEPTION: {e}")
            import traceback as _tb
            _log(f"[SSE] traceback: {_tb.format_exc()}")
            log_line("agent_route_stream_sse_failed", {"error": str(e), "trace": _tb.format_exc()})
            yield f"event: error\ndata: {_json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# AlphaFold API endpoints
@app.post("/api/alphafold/fold")
@limiter.limit("5/minute")
async def alphafold_fold(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        body = await request.json()
        sequence = body.get("sequence")
        parameters = body.get("parameters", {})
        job_id = body.get("jobId")
        
        # Comprehensive logging
        log_line("alphafold_request", {
            "jobId": job_id,
            "sequence_length": len(sequence) if sequence else 0,
            "parameters": parameters,
            "client_ip": get_remote_address(request)
        })
        
        if not sequence or not job_id:
            log_line("alphafold_validation_failed", {
                "missing_sequence": not sequence,
                "missing_jobId": not job_id,
                "jobId": job_id
            })
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "error": "Missing sequence or jobId",
                    "errorCode": "MISSING_PARAMETERS",
                    "userMessage": "Required parameters are missing"
                }
            )
        
        # Queue background job and return 202 Accepted immediately
        log_line("alphafold_submitting", {
            "jobId": job_id,
            "handler": "alphafold_handler.submit_folding_job (background)"
        })
        # Mark job as queued
        try:
            alphafold_handler.active_jobs[job_id] = "queued"
        except Exception:
            pass

        # Run the folding job asynchronously
        import asyncio as _asyncio
        _asyncio.create_task(
            alphafold_handler.submit_folding_job({
                "sequence": sequence,
                "parameters": parameters,
                "jobId": job_id,
                "userId": user.get("id"),
            })
        )

        return JSONResponse(
            status_code=202,
            content={
                "status": "accepted",
                "jobId": job_id,
                "message": "Folding job accepted. Poll /api/alphafold/status/{job_id} for updates."
            }
        )
        
    except Exception as e:
        log_line("alphafold_fold_failed", {"error": str(e), "trace": traceback.format_exc()})
        return JSONResponse(
            status_code=500, 
            content={
                "status": "error",
                "error": "",  # Empty for frontend error handling
                "errorCode": "INTERNAL_ERROR",
                "userMessage": "An unexpected error occurred",
                "technicalMessage": str(e) if DEBUG_API else "Internal server error"
            }
        )


@app.get("/api/alphafold/status/{job_id}")
@limiter.limit("30/minute")
async def alphafold_status(request: Request, job_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        status = alphafold_handler.get_job_status(job_id, user_id=user.get("id"))
        return status
    except Exception as e:
        log_line("alphafold_status_failed", {"error": str(e), "trace": traceback.format_exc()})
        content = {"error": "alphafold_status_failed"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)


@app.post("/api/alphafold/cancel/{job_id}")
@limiter.limit("10/minute")
async def alphafold_cancel(request: Request, job_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        result = alphafold_handler.cancel_job(job_id, user_id=user.get("id"))
        return result
    except Exception as e:
        log_line("alphafold_cancel_failed", {"error": str(e), "trace": traceback.format_exc()})
        content = {"error": "alphafold_cancel_failed"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)


# PDB upload utilities -----------------------------------------------------


@app.post("/api/upload/pdb")
@limiter.limit("20/minute")
async def upload_pdb(
    request: Request,
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(get_current_user)
):
    _ = request
    try:
        contents = await file.read()
        user_id = user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found")
        metadata = save_uploaded_pdb(file.filename, contents, user_id)
        log_line(
            "pdb_upload_success",
            {
                "filename": file.filename,
                "file_id": metadata["file_id"],
                "size": metadata.get("size"),
                "chains": metadata.get("chains"),
            },
        )
        return {
            "status": "success",
            "message": "File uploaded",
            "file_info": {
                "filename": metadata.get("filename"),
                "file_id": metadata.get("file_id"),
                "file_url": f"/api/upload/pdb/{metadata.get('file_id')}",
                "file_path": metadata.get("stored_path"),
                "size": metadata.get("size"),
                "atoms": metadata.get("atoms"),
                "chains": metadata.get("chains", []),
                "chain_residue_counts": metadata.get("chain_residue_counts", {}),
                "total_residues": metadata.get("total_residues"),
            },
        }
    except HTTPException as exc:
        raise exc
    except Exception as e:
        log_line("pdb_upload_failed", {"error": str(e), "trace": traceback.format_exc()})
        raise HTTPException(status_code=500, detail="Failed to upload PDB file")


@app.post("/api/upload/pdb/from-content")
@limiter.limit("30/minute")
async def upload_pdb_from_content(
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Store PDB content from message results (AlphaFold, RFdiffusion, OpenFold2) and return file_id for clean API URLs."""
    _ = request
    try:
        body = await request.json()
        pdb_content = body.get("pdbContent") or body.get("pdb_content")
        filename = body.get("filename", "structure.pdb")
        if not pdb_content:
            raise HTTPException(status_code=400, detail="pdbContent is required")
        if not filename.lower().endswith(".pdb"):
            filename = f"{filename}.pdb" if not filename.endswith(".pdb") else "structure.pdb"
        user_id = user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found")
        contents = pdb_content.encode("utf-8") if isinstance(pdb_content, str) else pdb_content
        metadata = save_uploaded_pdb(filename, contents, user_id)
        return {
            "status": "success",
            "message": "PDB stored",
            "file_info": {
                "filename": metadata.get("filename"),
                "file_id": metadata.get("file_id"),
                "file_url": f"/api/upload/pdb/{metadata.get('file_id')}",
                "atoms": metadata.get("atoms"),
                "chains": metadata.get("chains", []),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        log_line("pdb_from_content_failed", {"error": str(e), "trace": traceback.format_exc()})
        raise HTTPException(status_code=500, detail="Failed to store PDB content")


@app.post("/api/smiles/to-structure")
@limiter.limit("30/minute")
async def smiles_to_structure_endpoint(
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Convert SMILES to 3D structure (PDB or SDF) for loading in the MolStar viewer."""
    try:
        body = await request.json()
        smiles = (body.get("smiles") or "").strip()
        fmt = (body.get("format") or "pdb").lower()
        if fmt not in ("pdb", "sdf"):
            fmt = "pdb"
        if not smiles:
            return JSONResponse(
                status_code=400,
                content={
                    "userMessage": "SMILES string is required.",
                    "technicalMessage": "Request body must include a non-empty 'smiles' field.",
                },
            )
        content, filename = smiles_to_structure(smiles, fmt)
        return {
            "content": content,
            "filename": filename,
            "format": fmt,
        }
    except ValueError as e:
        log_line("smiles_conversion_validation_failed", {"error": str(e), "smiles_len": len(smiles)})
        return JSONResponse(
            status_code=400,
            content={
                "userMessage": str(e) or "Invalid SMILES or conversion failed.",
                "technicalMessage": str(e),
            },
        )
    except RuntimeError as e:
        log_line("smiles_conversion_runtime_failed", {"error": str(e)})
        return JSONResponse(
            status_code=503,
            content={
                "userMessage": "SMILES conversion is not available (RDKit not installed).",
                "technicalMessage": str(e),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        log_line("smiles_conversion_failed", {"error": str(e), "trace": traceback.format_exc()})
        return JSONResponse(
            status_code=500,
            content={
                "userMessage": "Failed to convert SMILES to structure.",
                "technicalMessage": str(e),
            },
        )


@app.get("/api/upload/pdb/{file_id}")
@limiter.limit("30/minute")
async def download_uploaded_pdb(request: Request, file_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    _ = request
    metadata = get_uploaded_pdb(file_id, user["id"])
    if not metadata:
        raise HTTPException(status_code=404, detail="Uploaded file not found")
    return FileResponse(
        metadata["absolute_path"],
        media_type="chemical/x-pdb",
        filename=metadata.get("filename") or f"{file_id}.pdb",
    )


# User file management endpoints -----------------------------------------


@app.get("/api/files")
@limiter.limit("30/minute")
async def get_user_files_endpoint(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    """List all files for the current user. Files are already user-scoped in the database."""
    _ = request
    try:
        log_line("user_files_request", {"user_id": user["id"]})
        base_dir = Path(__file__).parent
        all_files = []
        
        # Get all user files (already filtered by user_id in list_user_files)
        user_files = list_user_files(user["id"])
        log_line("user_files_raw", {"user_id": user["id"], "count": len(user_files)})
        
        for file_entry in user_files:
            file_type = file_entry.get("file_type", "")
            file_id = file_entry.get("id", "")
            stored_path_str = file_entry.get("stored_path", "")
            filename = file_entry.get("original_filename", f"{file_id}")
            
            log_line("processing_file", {
                "file_id": file_id,
                "file_type": file_type,
                "stored_path": stored_path_str,
                "filename": filename
            })
            
            if stored_path_str:
                file_path = base_dir / stored_path_str
                file_exists = file_path.exists()
                log_line("file_path_check", {
                    "file_id": file_id,
                    "stored_path": stored_path_str,
                    "absolute_path": str(file_path),
                    "exists": file_exists
                })
                
                if file_exists:
                    # Determine download URL based on file type
                    if file_type == "upload":
                        download_url = f"/api/upload/pdb/{file_id}"
                    elif file_type == "proteinmpnn":
                        download_url = f"/api/proteinmpnn/result/{file_id}"
                    elif file_type == "openfold2":
                        download_url = f"/api/openfold2/result/{file_id}"
                    else:
                        # For other types, use generic download endpoint
                        download_url = f"/api/files/{file_id}/download"
                    
                    # Parse metadata if it's a JSON string
                    metadata = file_entry.get("metadata", {})
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except json.JSONDecodeError:
                            metadata = {}
                    
                    file_size = file_entry.get("size", 0)
                    if file_size == 0:
                        try:
                            file_size = file_path.stat().st_size
                        except OSError:
                            file_size = 0
                    
                    all_files.append({
                        "file_id": file_id,
                        "type": file_type,
                        "filename": filename,
                        "file_path": stored_path_str,
                        "size": file_size,
                        "download_url": download_url,
                        "metadata": metadata,
                    })
                else:
                    log_line("file_not_found", {
                        "file_id": file_id,
                        "expected_path": str(file_path)
                    })
        
        log_line("user_files_loaded", {"user_id": user["id"], "file_count": len(all_files)})
        
        return {
            "status": "success",
            "files": all_files,
        }
    except Exception as e:
        log_line("user_files_list_failed", {"error": str(e), "trace": traceback.format_exc(), "user_id": user["id"]})
        content = {"error": "Failed to list user files"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)


@app.get("/api/files/{file_id}/download")
@limiter.limit("30/minute")
async def download_user_file(request: Request, file_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """Download a user file. Verifies ownership."""
    _ = request
    try:
        # Get file path with ownership verification
        file_path = get_user_file_path(file_id, user["id"])
        
        # Get file metadata for filename
        file_metadata = get_file_metadata(file_id, user["id"])
        filename = file_metadata.get("original_filename", f"{file_id}.pdb") if file_metadata else f"{file_id}.pdb"
        
        # Determine media type based on file extension
        media_type = "chemical/x-pdb" if filename.lower().endswith(".pdb") else "application/octet-stream"
        
        log_line("file_downloaded", {"file_id": file_id, "user_id": user["id"], "path": str(file_path)})
        
        return FileResponse(
            file_path,
            media_type=media_type,
            filename=filename,
        )
    except HTTPException:
        raise
    except Exception as e:
        log_line("file_download_failed", {"error": str(e), "trace": traceback.format_exc()})
        raise HTTPException(status_code=500, detail="Failed to download file")


@app.get("/api/files/{file_id}")
@limiter.limit("30/minute")
async def get_user_file_content(request: Request, file_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """Get file content as JSON (for editor/viewer). Verifies ownership."""
    _ = request
    try:
        # Get file path with ownership verification
        file_path = get_user_file_path(file_id, user["id"])
        
        # Get file metadata
        file_metadata = get_file_metadata(file_id, user["id"])
        if not file_metadata:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Read file content
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # If text decoding fails, return as base64
            import base64
            content = base64.b64encode(file_path.read_bytes()).decode("utf-8")
            return {
                "status": "success",
                "file_id": file_id,
                "filename": file_metadata.get("original_filename", f"{file_id}.pdb"),
                "content": content,
                "encoding": "base64",
                "type": file_metadata.get("file_type", "unknown")
            }
        
        log_line("file_content_accessed", {"file_id": file_id, "user_id": user["id"], "path": str(file_path)})
        
        return {
            "status": "success",
            "file_id": file_id,
            "filename": file_metadata.get("original_filename", f"{file_id}.pdb"),
            "content": content,
            "type": file_metadata.get("file_type", "unknown")
        }
    except HTTPException:
        raise
    except Exception as e:
        log_line("file_content_failed", {"error": str(e), "trace": traceback.format_exc()})
        raise HTTPException(status_code=500, detail="Failed to read file content")


@app.delete("/api/files/{file_id}")
@limiter.limit("10/minute")
async def delete_user_file(request: Request, file_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """Delete a user file. Verifies ownership."""
    _ = request
    try:
        # Verify ownership
        if not verify_file_ownership(file_id, user["id"]):
            raise HTTPException(status_code=403, detail="File not found or access denied")
        
        # Get file metadata
        file_metadata = get_file_metadata(file_id, user["id"])
        if not file_metadata:
            raise HTTPException(status_code=404, detail="File not found")
        
        base_dir = Path(__file__).parent
        stored_path = file_metadata.get("stored_path")
        
        if stored_path:
            file_path = base_dir / stored_path
            if file_path.exists():
                file_path.unlink()
                log_line("file_deleted", {"file_id": file_id, "user_id": user["id"], "path": str(file_path)})
        
        # Delete from database
        with get_db() as conn:
            conn.execute("DELETE FROM user_files WHERE id = ? AND user_id = ?", (file_id, user["id"]))
            # Also remove from session_files associations
            conn.execute("DELETE FROM session_files WHERE file_id = ? AND user_id = ?", (file_id, user["id"]))
        
        return {"status": "success", "message": "File deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        log_line("file_delete_failed", {"error": str(e), "trace": traceback.format_exc(), "file_id": file_id, "user_id": user["id"]})
        content = {"error": "Failed to delete file"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)


# ProteinMPNN endpoints ---------------------------------------------------


@app.get("/api/proteinmpnn/sources")
@limiter.limit("30/minute")
async def proteinmpnn_sources(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    _ = request
    try:
        user_id = user.get("id")
        sources = proteinmpnn_handler.list_available_sources(user_id=user_id)
        return {"status": "success", "sources": sources}
    except Exception as e:
        log_line("proteinmpnn_sources_failed", {"error": str(e), "trace": traceback.format_exc()})
        content = {"error": "proteinmpnn_sources_failed"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)


@app.post("/api/proteinmpnn/design")
@limiter.limit("5/minute")
async def proteinmpnn_design(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    body = await request.json()
    job_id = body.get("jobId")

    if not job_id:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error": "Missing jobId",
                "errorCode": "MISSING_PARAMETERS",
                "userMessage": "Required parameters are missing",
            },
        )

    user_id = user.get("id")
    job_payload = {
        "jobId": job_id,
        "parameters": body.get("parameters", {}),
        "pdbSource": body.get("pdbSource"),
        "sourceJobId": body.get("sourceJobId"),
        "uploadId": body.get("uploadId"),
        "pdbPath": body.get("pdbPath"),
        "pdbContent": body.get("pdbContent"),
        "source": body.get("source"),
        "userId": user_id,
    }

    try:
        proteinmpnn_handler.validate_job(job_payload, user_id=user_id)
    except Exception as e:
        log_line(
            "proteinmpnn_validation_failed",
            {"error": str(e), "jobId": job_id},
        )
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error": str(e),
                "errorCode": "INVALID_INPUT",
                "userMessage": "ProteinMPNN request is invalid",
            },
        )

    try:
        proteinmpnn_handler.active_jobs[job_id] = "queued"
    except Exception:
        pass

    log_line(
        "proteinmpnn_request",
        {
            "jobId": job_id,
            "pdbSource": job_payload.get("pdbSource"),
            "sourceJobId": job_payload.get("sourceJobId"),
            "uploadId": job_payload.get("uploadId"),
        },
    )

    asyncio.create_task(proteinmpnn_handler.submit_design_job(job_payload))

    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "jobId": job_id,
            "message": "ProteinMPNN job accepted. Poll /api/proteinmpnn/status/{job_id} for updates.",
        },
    )


@app.get("/api/proteinmpnn/status/{job_id}")
@limiter.limit("30/minute")
async def proteinmpnn_status(request: Request, job_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = user.get("id")
        status = proteinmpnn_handler.get_job_status(job_id, user_id=user_id)
        return status
    except Exception as e:
        log_line("proteinmpnn_status_failed", {"error": str(e), "trace": traceback.format_exc()})
        content = {"error": "proteinmpnn_status_failed"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)


@app.get("/api/proteinmpnn/result/{job_id}")
@limiter.limit("30/minute")
async def proteinmpnn_result(request: Request, job_id: str, user: Dict[str, Any] = Depends(get_current_user), fmt: str = "json"):
    user_id = user.get("id")
    try:
        result = proteinmpnn_handler.get_job_result(job_id, user_id=user_id)
        if not result:
            raise HTTPException(status_code=404, detail="ProteinMPNN result not found")

        if fmt == "json":
            return result
        if fmt == "fasta":
            result_dir = proteinmpnn_handler.get_result_dir(job_id, user_id=user_id)
            if not result_dir:
                raise HTTPException(status_code=404, detail="ProteinMPNN result not found")
            fasta_path = result_dir / "designed_sequences.fasta"
            if not fasta_path.exists():
                raise HTTPException(status_code=404, detail="FASTA output not available")
            return FileResponse(
                fasta_path,
                media_type="text/plain",
                filename=f"proteinmpnn_{job_id}.fasta",
            )
        if fmt == "raw":
            result_dir = proteinmpnn_handler.get_result_dir(job_id, user_id=user_id)
            if not result_dir:
                raise HTTPException(status_code=404, detail="ProteinMPNN result not found")
            raw_path = result_dir / "raw_data.json"
            if raw_path.exists():
                return FileResponse(
                    raw_path,
                    media_type="application/json",
                    filename=f"proteinmpnn_{job_id}_raw.json",
                )
            raise HTTPException(status_code=404, detail="Raw output not available")

        raise HTTPException(status_code=400, detail="Unsupported format requested")
    except HTTPException as exc:
        raise exc
    except Exception as e:
        log_line("proteinmpnn_result_failed", {"error": str(e), "trace": traceback.format_exc()})
        content = {"error": "proteinmpnn_result_failed"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)


# RFdiffusion API endpoints
async def _generate_error_ai_summary(
    error_msg: str,
    error_code: str,
    original_error: str,
    feature: str = "RFdiffusion",
    parameters: Optional[Dict] = None,
) -> str:
    """Generate an AI-powered user-friendly error summary using a fast LLM model.
    
    Returns a helpful natural-language explanation of the error and how to fix it.
    Falls back to a structured message if the LLM call fails.
    """
    try:
        from .agents.runner import _get_openrouter_api_key
        from .agents.runner_utils import _load_model_map

        model_map = _load_model_map()
        model_id = model_map.get("anthropic/claude-3-haiku", "anthropic/claude-3-haiku")
        api_key = _get_openrouter_api_key()

        if not api_key:
            return _build_fallback_error_summary(error_msg, original_error, feature, parameters)
        
        # Build context about the parameters
        param_context = ""
        if parameters:
            safe_params = {k: v for k, v in parameters.items() if k != "input_pdb" and not isinstance(v, bytes)}
            if safe_params:
                param_context = f"\nUser's parameters: {json.dumps(safe_params, default=str)}"
        
        prompt = f"""You are a helpful protein design assistant. The user tried to run {feature} protein design and got an error. 
Write a brief, friendly explanation (2-4 sentences) that:
1. Explains what went wrong in simple terms
2. Tells the user specifically what to fix
3. Is encouraging and helpful

Error code: {error_code}
Error message: {error_msg}
Original API error: {original_error}{param_context}

IMPORTANT: Be specific about what went wrong. If residues are mentioned, explain what that means. If parameters are wrong, say which ones.
Do NOT use markdown formatting. Write plain text only. Do NOT repeat the error code."""

        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": os.getenv("APP_ORIGIN", "http://localhost:5173"),
                    "X-Title": "NovoProtein AI",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.3,
                },
            )
            response.raise_for_status()
            data = response.json()
            summary = data["choices"][0]["message"]["content"].strip()
            return summary
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            log_line("ai_error_summary_failed", {"error": "OpenRouter API key invalid or missing (401)"})
        else:
            log_line("ai_error_summary_failed", {"error": str(e)})
        return _build_fallback_error_summary(error_msg, original_error, feature, parameters)
    except Exception as e:
        log_line("ai_error_summary_failed", {"error": str(e)})
        return _build_fallback_error_summary(error_msg, original_error, feature, parameters)


def _build_fallback_error_summary(
    error_msg: str, original_error: str, feature: str, parameters: Optional[Dict] = None
) -> str:
    """Build a structured fallback error summary without LLM."""
    parts = [f"Your {feature} protein design job encountered an error."]
    
    # Add specific detail from the original error
    if original_error and original_error != error_msg:
        parts.append(f"The API reported: \"{original_error}\"")
    elif error_msg:
        parts.append(f"Details: {error_msg}")
    
    # Add parameter-aware suggestions
    if parameters:
        hotspots = parameters.get("hotspot_res", [])
        if hotspots and ("residue" in error_msg.lower() or "422" in error_msg):
            parts.append(f"This likely means the specified hotspot residues ({', '.join(hotspots) if isinstance(hotspots, list) else hotspots}) don't exist in your PDB file. Try checking the residue numbering and chain IDs in your structure.")
        elif "pdb" in error_msg.lower():
            parts.append("Please verify that your PDB file is valid and contains the expected chains and residues.")
    
    parts.append("You can try adjusting your parameters and submitting again.")
    return " ".join(parts)


@app.post("/api/rfdiffusion/design")
@limiter.limit("5/minute")
async def rfdiffusion_design(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        body = await request.json()
        parameters = body.get("parameters", {})
        job_id = body.get("jobId")
        session_id = body.get("sessionId")
        
        if not job_id:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "error": "Missing jobId",
                    "errorCode": "MISSING_PARAMETERS",
                    "userMessage": "Required parameters are missing"
                }
            )
        
        log_line("rfdiffusion_design_request", {
            "job_id": job_id,
            "user_id": user["id"],
            "session_id": session_id,
            "has_parameters": bool(parameters)
        })
        
        result = await rfdiffusion_handler.submit_design_job({
            "parameters": parameters,
            "jobId": job_id,
            "userId": user["id"],
            "sessionId": session_id
        })
        
        # Check if result contains an error and return appropriate HTTP status
        if result.get("status") == "error":
            error_msg = result.get("error", "Unknown error")
            error_code = result.get("errorCode", "DESIGN_FAILED")
            original_error = result.get("originalError", error_msg)
            
            # Generate AI-powered error summary
            ai_summary = await _generate_error_ai_summary(
                error_msg=error_msg,
                error_code=error_code,
                original_error=original_error,
                feature="RFdiffusion",
                parameters=parameters,
            )
            
            # Check for specific error types
            if "API key not configured" in error_msg or "NVCF_RUN_KEY" in error_msg:
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "error",
                        "errorCode": "RFDIFFUSION_API_NOT_CONFIGURED",
                        "userMessage": "RFdiffusion service is not available. API key not configured.",
                        "technicalMessage": error_msg,
                        "originalError": original_error,
                        "aiSummary": ai_summary,
                        "suggestions": [
                            {
                                "action": "Contact administrator",
                                "description": "The RFdiffusion service requires NVIDIA API key configuration",
                                "type": "contact",
                                "priority": 1
                            }
                        ]
                    }
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "error",
                        "errorCode": error_code,
                        "userMessage": error_msg,
                        "technicalMessage": original_error,
                        "originalError": original_error,
                        "aiSummary": ai_summary,
                    }
                )
        
        return result
        
    except Exception as e:
        log_line("rfdiffusion_design_failed", {"error": str(e), "trace": traceback.format_exc()})
        
        # Safely try to get parameters from the request body
        try:
            exception_params = parameters if 'parameters' in dir() else None
        except Exception:
            exception_params = None
        
        # Generate AI summary even for unhandled exceptions
        ai_summary = await _generate_error_ai_summary(
            error_msg=str(e),
            error_code="INTERNAL_ERROR",
            original_error=str(e),
            feature="RFdiffusion",
            parameters=exception_params,
        )
        
        return JSONResponse(
            status_code=500, 
            content={
                "status": "error",
                "errorCode": "INTERNAL_ERROR",
                "userMessage": "An unexpected error occurred",
                "technicalMessage": str(e) if DEBUG_API else "Internal server error",
                "originalError": str(e) if DEBUG_API else "",
                "aiSummary": ai_summary,
            }
        )


@app.get("/api/rfdiffusion/status/{job_id}")
@limiter.limit("30/minute")
async def rfdiffusion_status(request: Request, job_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        status = rfdiffusion_handler.get_job_status(job_id, user_id=user.get("id"))
        
        # If the job errored, generate an AI summary on the first status check
        if status.get("status") == "error" and "aiSummary" not in status:
            error_msg = status.get("error", "Job failed")
            error_code = status.get("errorCode", "UNKNOWN_ERROR")
            original_error = status.get("originalError", error_msg)
            params = status.get("parameters", {})
            
            ai_summary = await _generate_error_ai_summary(
                error_msg=error_msg,
                error_code=error_code,
                original_error=original_error,
                feature="RFdiffusion",
                parameters=params,
            )
            status["aiSummary"] = ai_summary
            
            # Cache the AI summary in job_results so we don't regenerate
            if job_id in rfdiffusion_handler.job_results:
                rfdiffusion_handler.job_results[job_id]["aiSummary"] = ai_summary
        
        return status
    except Exception as e:
        log_line("rfdiffusion_status_failed", {"error": str(e), "trace": traceback.format_exc()})
        content = {"error": "rfdiffusion_status_failed"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)


@app.post("/api/rfdiffusion/cancel/{job_id}")
@limiter.limit("10/minute")
async def rfdiffusion_cancel(request: Request, job_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        result = rfdiffusion_handler.cancel_job(job_id, user_id=user.get("id"))
        return result
    except Exception as e:
        log_line("rfdiffusion_cancel_failed", {"error": str(e), "trace": traceback.format_exc()})
        content = {"error": "rfdiffusion_cancel_failed"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)


# OpenFold2 API endpoints (blocking prediction)
@app.post("/api/openfold2/predict")
@limiter.limit("5/minute")
async def openfold2_predict(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        body = await request.json()
        sequence = body.get("sequence")
        alignments = body.get("alignments")
        alignments_raw = body.get("alignmentsRaw")  # Raw a3m file content
        templates = body.get("templates")
        templates_raw = body.get("templatesRaw")  # Raw mmCIF template file content (HHR no longer supported in v2.0+)
        relax_prediction = body.get("relax_prediction", False)
        job_id = body.get("jobId")
        session_id = body.get("sessionId")

        if not sequence:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "error": "Missing sequence",
                    "code": "SEQUENCE_EMPTY",
                },
            )

        log_line("openfold2_predict_request", {
            "job_id": job_id,
            "user_id": user["id"],
            "session_id": session_id,
            "sequence_length": len(sequence) if sequence else 0,
        })

        result = await openfold2_handler.process_predict_request(
            sequence=sequence,
            alignments=alignments,
            alignments_raw=alignments_raw,
            templates=templates,
            templates_raw=templates_raw,
            relax_prediction=relax_prediction,
            job_id=job_id,
            session_id=session_id,
            user_id=user["id"],
        )

        if result.get("status") == "error":
            code = result.get("code", "API_ERROR")
            log_line("openfold2_predict_error", {"code": code, "error": result.get("error", "")[:500]})
            if code == "API_KEY_MISSING":
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "error",
                        "error": result.get("error", "OpenFold2 service not available"),
                        "code": code,
                    },
                )
            return JSONResponse(
                status_code=400 if code in ("SEQUENCE_EMPTY", "SEQUENCE_TOO_LONG", "SEQUENCE_INVALID", "MSA_FORMAT_INVALID", "TEMPLATE_FORMAT_INVALID") else 502,
                content=result,
            )

        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        log_line("openfold2_predict_failed", {"error": str(e), "trace": traceback.format_exc()})
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e) if DEBUG_API else "An unexpected error occurred",
                "code": "INTERNAL_ERROR",
            },
        )


@app.get("/api/openfold2/result/{job_id}")
@limiter.limit("30/minute")
async def openfold2_result(request: Request, job_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        file_path = get_user_file_path(job_id, user["id"])
        return FileResponse(
            file_path,
            media_type="chemical/x-pdb",
            filename=f"openfold2_{job_id}.pdb",
        )
    except HTTPException as exc:
        raise exc
    except Exception as e:
        log_line("openfold2_result_failed", {"error": str(e), "job_id": job_id})
        raise HTTPException(status_code=404, detail="OpenFold2 result not found")


# DiffDock API endpoints (blocking prediction)
@app.post("/api/diffdock/predict")
@limiter.limit("5/minute")
async def diffdock_predict(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        body = await request.json()
        protein_file_id = body.get("protein_file_id")
        protein_content = body.get("protein_content")
        ligand_sdf_content = body.get("ligand_sdf_content")
        parameters = body.get("parameters", {})
        job_id = body.get("job_id") or body.get("jobId")
        session_id = body.get("session_id") or body.get("sessionId")

        if not ligand_sdf_content:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "errorCode": "VALIDATION",
                    "userMessage": "Ligand SDF content is required.",
                },
            )
        if protein_file_id and protein_content:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "errorCode": "VALIDATION",
                    "userMessage": "Provide exactly one: protein_file_id or protein_content.",
                },
            )
        if not protein_file_id and not protein_content:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "errorCode": "VALIDATION",
                    "userMessage": "Provide protein_file_id (uploaded PDB) or protein_content (PDB text).",
                },
            )

        log_line("diffdock_predict_request", {
            "job_id": job_id,
            "user_id": user["id"],
            "session_id": session_id,
            "has_protein_file": bool(protein_file_id),
        })

        result = await diffdock_handler.submit_dock_job(
            protein_file_id=protein_file_id or None,
            protein_content=protein_content or None,
            ligand_sdf_content=ligand_sdf_content,
            parameters=parameters,
            user_id=user["id"],
            session_id=session_id,
            job_id=job_id,
        )

        if result.get("status") == "error":
            user_msg = result.get("userMessage") or result.get("error") or "Docking failed"
            log_line("diffdock_predict_error", {
                "job_id": job_id,
                "errorCode": result.get("errorCode", "API_ERROR"),
                "userMessage": user_msg[:500],
            })
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "errorCode": result.get("errorCode", "API_ERROR"),
                    "userMessage": user_msg,
                },
            )

        return result
    except ValueError as e:
        if "NVCF_RUN_KEY" in str(e) or "API key" in str(e).lower():
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "errorCode": "API_KEY_MISSING",
                    "userMessage": "DiffDock service not available. Set NVCF_RUN_KEY.",
                },
            )
        raise
    except Exception as e:
        log_line("diffdock_predict_failed", {"error": str(e), "trace": traceback.format_exc()})
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "errorCode": "INTERNAL_ERROR",
                "userMessage": "An unexpected error occurred",
            },
        )


@app.get("/api/diffdock/result/{job_id}")
@limiter.limit("30/minute")
async def diffdock_result(request: Request, job_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        file_path = get_user_file_path(job_id, user["id"])
        return FileResponse(
            file_path,
            media_type="chemical/x-pdb",
            filename=f"diffdock_{job_id}.pdb",
        )
    except HTTPException as exc:
        raise exc
    except Exception as e:
        log_line("diffdock_result_failed", {"error": str(e), "job_id": job_id})
        raise HTTPException(status_code=404, detail="DiffDock result not found")


# ── Validation Endpoints ─────────────────────────────────────────

@app.post("/api/validation/validate")
@limiter.limit("10/minute")
async def validate_structure_endpoint(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    """Validate a PDB structure and return quality metrics."""
    try:
        from agents.handlers.validation import validation_handler
    except ImportError:
        from .agents.handlers.validation import validation_handler

    try:
        body = await request.json()
        pdb_content = body.get("pdb_content")
        file_id = body.get("file_id")
        user_id = user.get("id", "anonymous") if user else "anonymous"
        session_id = body.get("session_id")

        result = await validation_handler.process_validation_request(
            input_text="validate structure",
            context={
                "current_pdb_content": pdb_content,
                "file_id": file_id,
                "user_id": user_id,
                "session_id": session_id,
            },
        )

        if result.get("action") == "error":
            return JSONResponse(status_code=400, content=result)

        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        log_line("validation_failed", {"error": str(e), "trace": traceback.format_exc()})
        content = {"error": "validation_failed"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)


# Back-compat endpoints
@app.post("/api/generate")
async def generate(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        body = await request.json()
        prompt = body.get("prompt")
        if not isinstance(prompt, str):
            return {"error": "prompt is required"}
        res = await run_agent(
            agent=agents["code-builder"],
            user_text=prompt,
            current_code=body.get("currentCode"),
            history=body.get("history"),
            selection=body.get("selection"),
        )
        return res
    except Exception as e:
        log_line("generation_failed", {"error": str(e), "trace": traceback.format_exc()})
        content = {"error": "generation_failed"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)


@app.post("/api/chat")
async def chat(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        body = await request.json()
        prompt = body.get("prompt")
        if not isinstance(prompt, str):
            return {"error": "prompt is required"}
        res = await run_agent(
            agent=agents["bio-chat"],
            user_text=prompt,
            current_code=body.get("currentCode"),
            history=body.get("history"),
            selection=body.get("selection"),
        )
        return res
    except Exception as e:
        err_str = str(e)
        if "OpenRouter API key is missing" in err_str or "OpenRouter API key is invalid or missing" in err_str:
            return JSONResponse(status_code=503, content={"error": "api_key_missing", "message": err_str})
        log_line("chat_failed", {"error": err_str, "trace": traceback.format_exc()})
        content = {"error": "chat_failed"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)


@app.post("/api/chat/generate-title")
@limiter.limit("30/minute")
async def generate_chat_title(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    """Generate an AI-powered title for a chat session based on messages."""
    try:
        body = await request.json()
        messages = body.get("messages", [])
        
        if not messages or len(messages) < 2:
            return {"title": "New Chat"}
        
        # Get first user message and first AI response
        user_msg = next((m for m in messages if m.get("type") == "user"), None)
        ai_msg = next((m for m in messages if m.get("type") == "ai"), None)
        
        if not user_msg or not ai_msg:
            return {"title": "New Chat"}
        
        # Create prompt for title generation
        user_content = user_msg.get("content", "")[:200]
        ai_content = ai_msg.get("content", "")[:200]
        
        title_prompt = f"""Generate a concise, descriptive title (max 60 characters) for this chat conversation.

User: {user_content}
AI: {ai_content}

Return ONLY the title text, no quotes, no explanation. Make it specific and meaningful."""

        # Use a lightweight model for title generation (Haiku is fast and cheap)
        from .agents.runner import _get_openrouter_api_key
        from .agents.runner_utils import _load_model_map

        model_map = _load_model_map()
        model_id = model_map.get("anthropic/claude-3-haiku", "anthropic/claude-3-haiku")
        api_key = _get_openrouter_api_key()
        
        if not api_key:
            log_line("title_generation_failed", {"error": "API key missing"})
            return {"title": "New Chat"}
        
        # Call OpenRouter API using httpx for async
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": os.getenv("APP_ORIGIN", "http://localhost:5173"),
                    "X-Title": "NovoProtein AI",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_id,
                    "messages": [
                        {"role": "user", "content": title_prompt}
                    ],
                    "max_tokens": 30,
                    "temperature": 0.3,
                }
            )
            response.raise_for_status()
            result = response.json()
            title = result["choices"][0]["message"]["content"].strip()
            
            # Clean up title (remove quotes, limit length)
            title = title.strip('"\'')
            if len(title) > 60:
                title = title[:57] + "..."
            
            log_line("title_generated", {"title": title, "model": model_id})
            return {"title": title or "New Chat"}
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            log_line("title_generation_failed", {"error": "OpenRouter API key invalid or missing (401)"})
        elif e.response.status_code == 429:
            log_line("title_generation_failed", {"error": "OpenRouter rate limit (429); using fallback title"})
        else:
            log_line("title_generation_failed", {"error": str(e)})
        return {"title": "New Chat"}
    except Exception as e:
        log_line("title_generation_failed", {"error": str(e), "trace": traceback.format_exc()})
        return {"title": "New Chat"}
