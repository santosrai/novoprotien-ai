"""ProteinMPNN API endpoints."""

import asyncio
import traceback
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

try:
    from ...agents.handlers.proteinmpnn import proteinmpnn_handler
    from ...infrastructure.utils import log_line
    from ...api.middleware.auth import get_current_user
    from ...api.limiter import limiter, DEBUG_API
except ImportError:
    from agents.handlers.proteinmpnn import proteinmpnn_handler
    from infrastructure.utils import log_line
    from api.middleware.auth import get_current_user
    from api.limiter import limiter, DEBUG_API

router = APIRouter()


@router.get("/api/proteinmpnn/sources")
@limiter.limit("30/minute")
async def proteinmpnn_sources(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
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


@router.post("/api/proteinmpnn/design")
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
        log_line("proteinmpnn_validation_failed", {"error": str(e), "jobId": job_id})
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

    log_line("proteinmpnn_request", {
        "jobId": job_id,
        "pdbSource": job_payload.get("pdbSource"),
        "sourceJobId": job_payload.get("sourceJobId"),
        "uploadId": job_payload.get("uploadId"),
    })

    asyncio.create_task(proteinmpnn_handler.submit_design_job(job_payload))

    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "jobId": job_id,
            "message": "ProteinMPNN job accepted. Poll /api/proteinmpnn/status/{job_id} for updates.",
        },
    )


@router.get("/api/proteinmpnn/status/{job_id}")
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


@router.get("/api/proteinmpnn/result/{job_id}")
@limiter.limit("30/minute")
async def proteinmpnn_result(
    request: Request,
    job_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
    fmt: str = "json",
):
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
            return FileResponse(fasta_path, media_type="text/plain", filename=f"proteinmpnn_{job_id}.fasta")
        if fmt == "raw":
            result_dir = proteinmpnn_handler.get_result_dir(job_id, user_id=user_id)
            if not result_dir:
                raise HTTPException(status_code=404, detail="ProteinMPNN result not found")
            raw_path = result_dir / "raw_data.json"
            if raw_path.exists():
                return FileResponse(raw_path, media_type="application/json", filename=f"proteinmpnn_{job_id}_raw.json")
            raise HTTPException(status_code=404, detail="Raw output not available")

        raise HTTPException(status_code=400, detail="Unsupported format requested")
    except HTTPException:
        raise
    except Exception as e:
        log_line("proteinmpnn_result_failed", {"error": str(e), "trace": traceback.format_exc()})
        content = {"error": "proteinmpnn_result_failed"}
        if DEBUG_API:
            content["detail"] = str(e)
        return JSONResponse(status_code=500, content=content)
