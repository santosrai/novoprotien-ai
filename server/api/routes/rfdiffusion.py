"""RFdiffusion API endpoints."""

import json
import os
import traceback
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

try:
    from ...agents.handlers.rfdiffusion import rfdiffusion_handler
    from ...domain.storage.protein_labels import register_protein_label
    from ...infrastructure.utils import log_line
    from ...api.middleware.auth import get_current_user
    from ...api.limiter import limiter, DEBUG_API
except ImportError:
    from agents.handlers.rfdiffusion import rfdiffusion_handler
    from domain.storage.protein_labels import register_protein_label
    from infrastructure.utils import log_line
    from api.middleware.auth import get_current_user
    from api.limiter import limiter, DEBUG_API

router = APIRouter()


# ---------------------------------------------------------------------------
# Error summary helpers (local to rfdiffusion)
# ---------------------------------------------------------------------------

async def _generate_error_ai_summary(
    error_msg: str,
    error_code: str,
    original_error: str,
    feature: str = "RFdiffusion",
    parameters: Optional[Dict] = None,
) -> str:
    """Generate an AI-powered user-friendly error summary using a fast LLM model."""
    try:
        try:
            from ...agents.runner import _get_openrouter_api_key
            from ...agents.runner_utils import _load_model_map
        except ImportError:
            from agents.runner import _get_openrouter_api_key
            from agents.runner_utils import _load_model_map

        model_map = _load_model_map()
        model_id = model_map.get("anthropic/claude-3-haiku", "anthropic/claude-3-haiku")
        api_key = _get_openrouter_api_key()

        if not api_key:
            return _build_fallback_error_summary(error_msg, original_error, feature, parameters)

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
            return data["choices"][0]["message"]["content"].strip()
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

    if original_error and original_error != error_msg:
        parts.append(f'The API reported: "{original_error}"')
    elif error_msg:
        parts.append(f"Details: {error_msg}")

    if parameters:
        hotspots = parameters.get("hotspot_res", [])
        if hotspots and ("residue" in error_msg.lower() or "422" in error_msg):
            parts.append(
                f"This likely means the specified hotspot residues ({', '.join(hotspots) if isinstance(hotspots, list) else hotspots}) "
                "don't exist in your PDB file. Try checking the residue numbering and chain IDs in your structure."
            )
        elif "pdb" in error_msg.lower():
            parts.append("Please verify that your PDB file is valid and contains the expected chains and residues.")

    parts.append("You can try adjusting your parameters and submitting again.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/api/rfdiffusion/design")
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
                    "userMessage": "Required parameters are missing",
                },
            )

        log_line("rfdiffusion_design_request", {
            "job_id": job_id,
            "user_id": user["id"],
            "session_id": session_id,
            "has_parameters": bool(parameters),
        })

        result = await rfdiffusion_handler.submit_design_job({
            "parameters": parameters,
            "jobId": job_id,
            "userId": user["id"],
            "sessionId": session_id,
        })

        if result.get("status") != "error" and session_id:
            file_id = result.get("file_id")
            try:
                label = register_protein_label(
                    session_id=session_id,
                    user_id=user["id"],
                    kind="design",
                    source_tool="RFdiffusion",
                    file_id=file_id,
                    job_id=job_id,
                )
                result["proteinLabel"] = label
            except Exception as label_err:
                log_line("protein_label_failed", {"error": str(label_err), "job_id": job_id})

        if result.get("status") == "error":
            error_msg = result.get("error", "Unknown error")
            error_code = result.get("errorCode", "DESIGN_FAILED")
            original_error = result.get("originalError", error_msg)

            ai_summary = await _generate_error_ai_summary(
                error_msg=error_msg,
                error_code=error_code,
                original_error=original_error,
                feature="RFdiffusion",
                parameters=parameters,
            )

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
                                "priority": 1,
                            }
                        ],
                    },
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
                    },
                )

        return result

    except Exception as e:
        log_line("rfdiffusion_design_failed", {"error": str(e), "trace": traceback.format_exc()})

        try:
            exception_params = parameters if "parameters" in dir() else None
        except Exception:
            exception_params = None

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
            },
        )


@router.get("/api/rfdiffusion/status/{job_id}")
@limiter.limit("30/minute")
async def rfdiffusion_status(request: Request, job_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        status = rfdiffusion_handler.get_job_status(job_id)

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

            if job_id in rfdiffusion_handler.job_results:
                rfdiffusion_handler.job_results[job_id]["aiSummary"] = ai_summary

        return status
    except Exception as e:
        log_line("rfdiffusion_status_failed", {"error": str(e), "trace": traceback.format_exc()})
        content = {"error": "rfdiffusion_status_failed"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)


@router.post("/api/rfdiffusion/cancel/{job_id}")
@limiter.limit("10/minute")
async def rfdiffusion_cancel(request: Request, job_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        result = rfdiffusion_handler.cancel_job(job_id)
        return result
    except Exception as e:
        log_line("rfdiffusion_cancel_failed", {"error": str(e), "trace": traceback.format_exc()})
        content = {"error": "rfdiffusion_cancel_failed"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)
