"""Protein label REST API endpoints."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

try:
    from ...domain.storage.protein_labels import (
        register_protein_label,
        get_protein_labels_for_session,
        get_protein_label_by_short_label,
    )
    from ...api.middleware.auth import get_current_user
    from ...api.limiter import limiter
except ImportError:
    from domain.storage.protein_labels import (
        register_protein_label,
        get_protein_labels_for_session,
        get_protein_label_by_short_label,
    )
    from api.middleware.auth import get_current_user
    from api.limiter import limiter

router = APIRouter(prefix="/api/proteins", tags=["proteins"])


class RegisterLabelRequest(BaseModel):
    sessionId: str
    kind: str
    sourceTool: Optional[str] = None
    fileId: Optional[str] = None
    jobId: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    preferredPrefix: Optional[str] = None


@router.post("")
@limiter.limit("30/minute")
async def create_protein_label(
    request: Request,
    body: RegisterLabelRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Register a new protein label for the given session."""
    _ = request
    try:
        label = register_protein_label(
            session_id=body.sessionId,
            user_id=user["id"],
            kind=body.kind,
            source_tool=body.sourceTool,
            file_id=body.fileId,
            job_id=body.jobId,
            metadata=body.metadata,
            preferred_prefix=body.preferredPrefix,
        )
        return {"status": "success", "label": label}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
@limiter.limit("60/minute")
async def list_protein_labels(
    request: Request,
    sessionId: str = Query(...),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """List all protein labels for a session."""
    _ = request
    labels = get_protein_labels_for_session(sessionId, user["id"])
    return {"status": "success", "labels": labels}


@router.get("/{short_label}")
@limiter.limit("60/minute")
async def get_protein_label(
    request: Request,
    short_label: str,
    sessionId: str = Query(...),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Lookup a single protein label by its short label within a session."""
    _ = request
    label = get_protein_label_by_short_label(sessionId, user["id"], short_label)
    if not label:
        raise HTTPException(status_code=404, detail="Protein label not found")
    return {"status": "success", "label": label}
