#!/usr/bin/env python3
"""
Job history and management API routes.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

try:
    from ...domain.protein.alphafold_job_service import AlphaFoldJobService
    from ...api.middleware.auth import get_current_user
except ImportError:
    from domain.protein.alphafold_job_service import AlphaFoldJobService
    from api.middleware.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

job_service = AlphaFoldJobService()


@router.get("/api/jobs/alphafold")
async def get_alphafold_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user: dict = Depends(get_current_user)
):
    """
    Get user's AlphaFold job history
    
    Args:
        status: Optional status filter (queued|running|completed|error|cancelled)
        limit: Maximum number of results (1-100)
        offset: Pagination offset
        user: Current authenticated user
        
    Returns:
        List of job dictionaries with metadata
    """
    try:
        jobs = job_service.get_user_jobs(
            user_id=user["id"],
            status=status,
            limit=limit,
            offset=offset
        )
        
        return {
            "jobs": jobs,
            "total": len(jobs),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Failed to get AlphaFold jobs for user {user['id']}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve job history")


@router.get("/api/jobs/alphafold/{job_id}")
async def get_alphafold_job(
    job_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get specific AlphaFold job details
    
    Args:
        job_id: Job identifier
        user: Current authenticated user
        
    Returns:
        Job dictionary with full details
    """
    try:
        job = job_service.get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Verify user owns the job
        if job["user_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return job
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get AlphaFold job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve job")
