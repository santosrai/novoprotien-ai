"""User reports API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional
from pydantic import BaseModel

from ..middleware.auth import get_current_user, require_admin
from ...domain.reports.service import (
    create_report,
    get_user_reports,
    get_all_reports,
    update_report_status,
    get_report_by_id
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


class ReportSubmit(BaseModel):
    """Model for report submission."""
    report_type: str
    title: str
    description: str


class ReportUpdate(BaseModel):
    """Model for report status update."""
    status: str
    admin_notes: Optional[str] = None
    priority: Optional[str] = None


@router.post("/submit")
async def submit_report(
    report_data: ReportSubmit,
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Submit a new report."""
    result = create_report(
        user["id"],
        report_data.report_type,
        report_data.title,
        report_data.description
    )
    return {"status": "success", **result}


@router.get("/my-reports")
async def my_reports(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Get user's reports."""
    reports = get_user_reports(user["id"])
    return {"status": "success", "reports": reports}


@router.get("/all")
async def all_reports(
    status_filter: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    """Get all reports (admin only)."""
    reports = get_all_reports(status_filter)
    return {"status": "success", "reports": reports}


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get a specific report."""
    report = get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Users can only see their own reports unless they're admin
    if report["user_id"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    return {"status": "success", "report": report}


@router.patch("/{report_id}")
async def update_report(
    report_id: str,
    update_data: ReportUpdate,
    admin: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    """Update report status (admin only)."""
    report = get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    update_report_status(
        report_id,
        update_data.status,
        admin["id"],
        update_data.admin_notes,
        update_data.priority
    )
    
    return {"status": "success", "message": "Report updated successfully"}

