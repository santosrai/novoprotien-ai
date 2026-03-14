"""ESMFold structure prediction API endpoints."""

import traceback
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

try:
    from ...agents.handlers.esmfold import esmfold_handler
    from ...domain.storage.protein_labels import register_protein_label
    from ...infrastructure.utils import log_line
    from ...api.middleware.auth import get_current_user
    from ...api.limiter import limiter, DEBUG_API
    from ...domain.storage.file_access import get_user_file_path
except ImportError:
    from agents.handlers.esmfold import esmfold_handler
    from domain.storage.protein_labels import register_protein_label
    from infrastructure.utils import log_line
    from api.middleware.auth import get_current_user
    from api.limiter import limiter, DEBUG_API
    from domain.storage.file_access import get_user_file_path

router = APIRouter()


@router.post("/api/esmfold/predict")
@limiter.limit("10/minute")
async def esmfold_predict(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    """Predict protein 3D structure using ESMFold (blocking, ≤400 residues, no MSA needed)."""
    try:
        body = await request.json()
        sequence = (body.get("sequence") or "").strip()
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

        log_line("esmfold_predict_request", {
            "job_id": job_id,
            "user_id": user["id"],
            "session_id": session_id,
            "sequence_length": len(sequence),
        })

        result = await esmfold_handler.process_predict_request(
            sequence=sequence,
            job_id=job_id,
            session_id=session_id,
            user_id=user["id"],
        )

        if result.get("status") == "error":
            code = result.get("code", "API_ERROR")
            log_line("esmfold_predict_error", {"code": code, "error": result.get("error", "")[:500]})

            if code == "API_KEY_MISSING":
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "error",
                        "error": result.get("error", "ESMFold service not available"),
                        "code": code,
                    },
                )

            http_status = 400 if code in (
                "SEQUENCE_EMPTY", "SEQUENCE_TOO_LONG", "SEQUENCE_TOO_SHORT", "SEQUENCE_INVALID"
            ) else 502
            return JSONResponse(status_code=http_status, content=result)

        if session_id and result.get("status") == "completed":
            file_id = result.get("file_id")
            try:
                label = register_protein_label(
                    session_id=session_id,
                    user_id=user["id"],
                    kind="folded",
                    source_tool="ESMFold",
                    file_id=file_id,
                    job_id=job_id,
                )
                result["proteinLabel"] = label
            except Exception as label_err:
                log_line("protein_label_failed", {"error": str(label_err), "job_id": job_id})

        return JSONResponse(status_code=200, content=result)

    except Exception as e:
        log_line("esmfold_predict_failed", {"error": str(e), "trace": traceback.format_exc()})
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e) if DEBUG_API else "An unexpected error occurred",
                "code": "INTERNAL_ERROR",
            },
        )


@router.get("/api/esmfold/result/{job_id}")
@limiter.limit("30/minute")
async def esmfold_result(request: Request, job_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """Download the predicted PDB file. Verifies ownership."""
    try:
        file_path = get_user_file_path(job_id, user["id"])
        return FileResponse(
            file_path,
            media_type="chemical/x-pdb",
            filename=f"esmfold_{job_id}.pdb",
        )
    except HTTPException as exc:
        raise exc
    except Exception as e:
        log_line("esmfold_result_failed", {"error": str(e), "job_id": job_id})
        raise HTTPException(status_code=404, detail="ESMFold result not found")
