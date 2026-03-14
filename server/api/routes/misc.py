"""Miscellaneous API endpoints: logs, validation, legacy chat/generate, title generation."""

import os
import traceback
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

try:
    from ...infrastructure.utils import log_line
    from ...api.middleware.auth import get_current_user, get_current_user_optional
    from ...api.limiter import limiter, DEBUG_API
except ImportError:
    from infrastructure.utils import log_line
    from api.middleware.auth import get_current_user, get_current_user_optional
    from api.limiter import limiter, DEBUG_API

router = APIRouter()


@router.post("/api/logs/error")
@limiter.limit("100/minute")
async def log_error(request: Request, user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Accept error logs from frontend (auth optional)."""
    try:
        body = await request.json()
        log_line("frontend_error", body)
        return {"status": "logged"}
    except Exception as e:
        log_line("error_logging_failed", {"error": str(e), "trace": traceback.format_exc()})
        return JSONResponse(status_code=500, content={"error": "logging_failed"})


@router.post("/api/validation/validate")
@limiter.limit("10/minute")
async def validate_structure_endpoint(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    """Validate a PDB structure and return quality metrics."""
    try:
        from agents.handlers.validation import validation_handler
    except ImportError:
        try:
            from ...agents.handlers.validation import validation_handler
        except ImportError:
            from agents.handlers.validation import validation_handler

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


@router.post("/api/generate")
async def generate(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    """Back-compat endpoint."""
    try:
        from agents.registry import agents
        from agents.runner import run_agent
    except ImportError:
        try:
            from ...agents.registry import agents
            from ...agents.runner import run_agent
        except ImportError:
            from agents.registry import agents
            from agents.runner import run_agent

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


@router.post("/api/chat")
async def chat(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    """Back-compat endpoint."""
    try:
        from agents.registry import agents
        from agents.runner import run_agent
    except ImportError:
        try:
            from ...agents.registry import agents
            from ...agents.runner import run_agent
        except ImportError:
            from agents.registry import agents
            from agents.runner import run_agent

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


@router.post("/api/chat/generate-title")
@limiter.limit("30/minute")
async def generate_chat_title(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    """Generate an AI-powered title for a chat session based on messages."""
    try:
        from agents.runner_utils import _load_model_map
        from agents.runner import _get_openrouter_api_key
    except ImportError:
        try:
            from ...agents.runner_utils import _load_model_map
            from ...agents.runner import _get_openrouter_api_key
        except ImportError:
            from agents.runner_utils import _load_model_map
            from agents.runner import _get_openrouter_api_key

    try:
        body = await request.json()
        messages = body.get("messages", [])

        if not messages or len(messages) < 2:
            return {"title": "New Chat"}

        user_msg = next((m for m in messages if m.get("type") == "user"), None)
        ai_msg = next((m for m in messages if m.get("type") == "ai"), None)

        if not user_msg or not ai_msg:
            return {"title": "New Chat"}

        user_content = user_msg.get("content", "")[:200]
        ai_content = ai_msg.get("content", "")[:200]

        title_prompt = f"""Generate a concise, descriptive title (max 60 characters) for this chat conversation.

User: {user_content}
AI: {ai_content}

Return ONLY the title text, no quotes, no explanation. Make it specific and meaningful."""

        model_map = _load_model_map()
        model_id = model_map.get("anthropic/claude-3-haiku", "anthropic/claude-3-haiku")
        api_key = _get_openrouter_api_key()

        if not api_key:
            log_line("title_generation_failed", {"error": "API key missing"})
            return {"title": "New Chat"}

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
                    "messages": [{"role": "user", "content": title_prompt}],
                    "max_tokens": 30,
                    "temperature": 0.3,
                },
            )
            response.raise_for_status()
            result = response.json()
            title = result["choices"][0]["message"]["content"].strip()
            title = title.strip("\"'")
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
