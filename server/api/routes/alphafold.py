"""AlphaFold API endpoints."""

import asyncio as _asyncio
import traceback
from typing import Any, Dict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from slowapi.util import get_remote_address

try:
    from ...agents.handlers.alphafold import alphafold_handler
    from ...infrastructure.utils import log_line
    from ...api.middleware.auth import get_current_user
    from ...api.limiter import limiter, DEBUG_API
except ImportError:
    from agents.handlers.alphafold import alphafold_handler
    from infrastructure.utils import log_line
    from api.middleware.auth import get_current_user
    from api.limiter import limiter, DEBUG_API

router = APIRouter()


@router.post("/api/alphafold/fold")
@limiter.limit("5/minute")
async def alphafold_fold(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        body = await request.json()
        sequence = body.get("sequence")
        parameters = body.get("parameters", {})
        job_id = body.get("jobId")

        log_line("alphafold_request", {
            "jobId": job_id,
            "sequence_length": len(sequence) if sequence else 0,
            "sequence_preview": sequence[:50] if sequence else None,
            "parameters": parameters,
            "client_ip": get_remote_address(request),
        })

        if not sequence or not job_id:
            log_line("alphafold_validation_failed", {
                "missing_sequence": not sequence,
                "missing_jobId": not job_id,
                "jobId": job_id,
            })
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "error": "Missing sequence or jobId",
                    "errorCode": "MISSING_PARAMETERS",
                    "userMessage": "Required parameters are missing",
                },
            )

        log_line("alphafold_submitting", {
            "jobId": job_id,
            "handler": "alphafold_handler.submit_folding_job (background)",
        })
        try:
            alphafold_handler.active_jobs[job_id] = "queued"
        except Exception:
            pass

        _asyncio.create_task(
            alphafold_handler.submit_folding_job({
                "sequence": sequence,
                "parameters": parameters,
                "jobId": job_id,
            })
        )

        return JSONResponse(
            status_code=202,
            content={
                "status": "accepted",
                "jobId": job_id,
                "message": "Folding job accepted. Poll /api/alphafold/status/{job_id} for updates.",
            },
        )

    except Exception as e:
        log_line("alphafold_fold_failed", {"error": str(e), "trace": traceback.format_exc()})
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": "",
                "errorCode": "INTERNAL_ERROR",
                "userMessage": "An unexpected error occurred",
                "technicalMessage": str(e) if DEBUG_API else "Internal server error",
            },
        )


@router.get("/api/alphafold/status/{job_id}")
@limiter.limit("30/minute")
async def alphafold_status(request: Request, job_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        status = alphafold_handler.get_job_status(job_id)
        return status
    except Exception as e:
        log_line("alphafold_status_failed", {"error": str(e), "trace": traceback.format_exc()})
        content = {"error": "alphafold_status_failed"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)


@router.post("/api/alphafold/cancel/{job_id}")
@limiter.limit("10/minute")
async def alphafold_cancel(request: Request, job_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        result = alphafold_handler.cancel_job(job_id)
        return result
    except Exception as e:
        log_line("alphafold_cancel_failed", {"error": str(e), "trace": traceback.format_exc()})
        content = {"error": "alphafold_cancel_failed"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)
