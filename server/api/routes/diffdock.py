"""DiffDock API endpoints."""

import traceback
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

try:
    from ...agents.handlers.diffdock import diffdock_handler
    from ...domain.storage.protein_labels import register_protein_label
    from ...infrastructure.utils import log_line
    from ...api.middleware.auth import get_current_user
    from ...api.limiter import limiter, DEBUG_API
    from ...domain.storage.file_access import get_user_file_path
except ImportError:
    from agents.handlers.diffdock import diffdock_handler
    from domain.storage.protein_labels import register_protein_label
    from infrastructure.utils import log_line
    from api.middleware.auth import get_current_user
    from api.limiter import limiter, DEBUG_API
    from domain.storage.file_access import get_user_file_path

router = APIRouter()


@router.post("/api/diffdock/predict")
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

        if session_id and result.get("status") != "error":
            file_id = result.get("file_id")
            try:
                label = register_protein_label(
                    session_id=session_id,
                    user_id=user["id"],
                    kind="docked",
                    source_tool="DiffDock",
                    file_id=file_id,
                    job_id=job_id,
                )
                result["proteinLabel"] = label
            except Exception as label_err:
                log_line("protein_label_failed", {"error": str(label_err), "job_id": job_id})

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


@router.get("/api/diffdock/result/{job_id}")
@limiter.limit("30/minute")
async def diffdock_result(request: Request, job_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        file_path = get_user_file_path(job_id, user["id"])
        return FileResponse(file_path, media_type="chemical/x-pdb", filename=f"diffdock_{job_id}.pdb")
    except HTTPException as exc:
        raise exc
    except Exception as e:
        log_line("diffdock_result_failed", {"error": str(e), "job_id": job_id})
        raise HTTPException(status_code=404, detail="DiffDock result not found")
