"""Health check endpoint."""

from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter()


@router.get("/api/health")
def health() -> Dict[str, Any]:
    return {"ok": True}

