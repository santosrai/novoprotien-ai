"""Credit check middleware for FastAPI."""

from fastapi import HTTPException, status, Depends
from typing import Optional, Dict, Any

from ...domain.credits.service import get_user_credits, CREDIT_COSTS
from .auth import get_current_user


def check_credits(action_type: str, required_credits: Optional[int] = None):
    """Dependency factory to check if user has sufficient credits."""
    async def credit_checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        cost = required_credits or CREDIT_COSTS.get(action_type, 0)
        if cost == 0:
            return user  # Free action
        
        user_credits = get_user_credits(user["id"])
        if user_credits < cost:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "Insufficient credits",
                    "required": cost,
                    "available": user_credits,
                    "action": action_type
                }
            )
        return user
    return credit_checker

