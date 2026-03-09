"""OpenFold2 API endpoints."""

import traceback
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

try:
    from ...agents.handlers.openfold2 import openfold2_handler
    from ...infrastructure.utils import log_line
    from ...api.middleware.auth import get_current_user
    from ...api.limiter import limiter, DEBUG_API
    from ...domain.storage.file_access import get_user_file_path
except ImportError:
    from agents.handlers.openfold2 import openfold2_handler
    from infrastructure.utils import log_line
    from api.middleware.auth import get_current_user
    from api.limiter import limiter, DEBUG_API
    from domain.storage.file_access import get_user_file_path

router = APIRouter()


@router.post("/api/openfold2/predict")
@limiter.limit("5/minute")
async def openfold2_predict(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        body = await request.json()
        sequence = body.get("sequence")
        alignments = body.get("alignments")
        alignments_raw = body.get("alignmentsRaw")
        templates = body.get("templates")
        templates_raw = body.get("templatesRaw")
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
                status_code=400 if code in (
                    "SEQUENCE_EMPTY", "SEQUENCE_TOO_LONG", "SEQUENCE_INVALID",
                    "MSA_FORMAT_INVALID", "TEMPLATE_FORMAT_INVALID"
                ) else 502,
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


@router.get("/api/openfold2/result/{job_id}")
@limiter.limit("30/minute")
async def openfold2_result(request: Request, job_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        file_path = get_user_file_path(job_id, user["id"])
        return FileResponse(file_path, media_type="chemical/x-pdb", filename=f"openfold2_{job_id}.pdb")
    except HTTPException as exc:
        raise exc
    except Exception as e:
        log_line("openfold2_result_failed", {"error": str(e), "job_id": job_id})
        raise HTTPException(status_code=404, detail="OpenFold2 result not found")
