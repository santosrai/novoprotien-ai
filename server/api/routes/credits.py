"""Credits API routes."""

from fastapi import APIRouter, Depends
from typing import Dict, Any

from ..middleware.auth import get_current_user
from ...domain.credits.service import get_user_credits, get_credit_history, get_usage_history

router = APIRouter(prefix="/api/credits", tags=["credits"])


@router.get("/balance")
async def get_balance(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Get user credit balance."""
    credits = get_user_credits(user["id"])
    return {"status": "success", "credits": credits}


@router.get("/history")
async def get_history(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Get credit transaction history."""
    history = get_credit_history(user["id"])
    return {"status": "success", "history": history}


@router.get("/usage")
async def get_usage(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Get usage history."""
    usage = get_usage_history(user["id"])
    return {"status": "success", "usage": usage}

