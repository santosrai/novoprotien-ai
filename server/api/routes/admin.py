"""Admin API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional
from pydantic import BaseModel

from ..middleware.auth import require_admin
from ...domain.user.service import (
    get_all_users,
    get_user_by_id,
    update_user_role,
    deactivate_user,
    activate_user
)
from ...domain.credits.service import add_credits, get_user_credits
from ...database.db import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])


class RoleUpdate(BaseModel):
    """Model for role update."""
    role: str


class CreditAdjustment(BaseModel):
    """Model for credit adjustment."""
    amount: int
    description: str


class StatusUpdate(BaseModel):
    """Model for status update."""
    is_active: bool


@router.get("/users")
async def list_users(admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    """List all users (admin only)."""
    users = get_all_users()
    return {"status": "success", "users": users}


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: str,
    admin: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    """Get user details (admin only)."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "success", "user": user}


@router.patch("/users/{user_id}/role")
async def update_user_role_endpoint(
    user_id: str,
    role_data: RoleUpdate,
    admin: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    """Update user role (admin only)."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_user_role(user_id, role_data.role)
    return {"status": "success", "message": "User role updated successfully"}


@router.post("/users/{user_id}/credits")
async def adjust_credits(
    user_id: str,
    credit_data: CreditAdjustment,
    admin: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    """Adjust user credits (admin only)."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    add_credits(user_id, credit_data.amount, credit_data.description, "admin_adjustment")
    new_balance = get_user_credits(user_id)
    
    return {
        "status": "success",
        "message": "Credits adjusted successfully",
        "new_balance": new_balance
    }


@router.patch("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    status_data: StatusUpdate,
    admin: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    """Activate/deactivate user (admin only)."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if status_data.is_active:
        activate_user(user_id)
    else:
        deactivate_user(user_id)
    
    return {"status": "success", "message": "User status updated successfully"}


@router.get("/stats")
async def get_stats(admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    """Get dashboard statistics (admin only)."""
    with get_db() as conn:
        # Total users
        total_users = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()["count"]
        
        # Active users
        active_users = conn.execute(
            "SELECT COUNT(*) as count FROM users WHERE is_active = 1"
        ).fetchone()["count"]
        
        # Total credits in system
        total_credits = conn.execute(
            "SELECT SUM(credits) as total FROM user_credits"
        ).fetchone()["total"] or 0
        
        # Pending reports
        pending_reports = conn.execute(
            "SELECT COUNT(*) as count FROM user_reports WHERE status = 'pending'"
        ).fetchone()["count"]
        
        # Recent signups (last 7 days)
        from datetime import datetime, timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_signups = conn.execute(
            "SELECT COUNT(*) as count FROM users WHERE created_at > ?",
            (week_ago,)
        ).fetchone()["count"]
    
    return {
        "status": "success",
        "stats": {
            "total_users": total_users,
            "active_users": active_users,
            "total_credits": total_credits,
            "pending_reports": pending_reports,
            "recent_signups": recent_signups
        }
    }

