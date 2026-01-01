"""Pipeline persistence API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
import json
import uuid
from datetime import datetime

from ...database.db import get_db
from ..middleware.auth import get_current_user

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])


@router.post("")
async def create_pipeline(
    pipeline_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create or save a pipeline."""
    pipeline_id = pipeline_data.get("id") or str(uuid.uuid4())
    name = pipeline_data.get("name", "Untitled Pipeline")
    description = pipeline_data.get("description")
    pipeline_json = json.dumps(pipeline_data)
    status_value = pipeline_data.get("status", "draft")
    
    with get_db() as conn:
        # Check if pipeline exists and belongs to user
        existing = conn.execute(
            "SELECT id FROM pipelines WHERE id = ? AND user_id = ?",
            (pipeline_id, user["id"]),
        ).fetchone()
        
        if existing:
            # Update existing pipeline
            conn.execute(
                """UPDATE pipelines 
                   SET name = ?, description = ?, pipeline_json = ?, status = ?, updated_at = ?
                   WHERE id = ? AND user_id = ?""",
                (name, description, pipeline_json, status_value, datetime.utcnow(), pipeline_id, user["id"]),
            )
        else:
            # Create new pipeline
            conn.execute(
                """INSERT INTO pipelines (id, user_id, name, description, pipeline_json, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pipeline_id,
                    user["id"],
                    name,
                    description,
                    pipeline_json,
                    status_value,
                    datetime.utcnow(),
                    datetime.utcnow(),
                ),
            )
    
    return {
        "status": "success",
        "pipeline_id": pipeline_id,
        "message": "Pipeline saved successfully",
    }


@router.get("")
async def list_pipelines(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """List all pipelines for the current user."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, name, description, status, created_at, updated_at
               FROM pipelines 
               WHERE user_id = ? 
               ORDER BY updated_at DESC""",
            (user["id"],),
        ).fetchall()
        
        pipelines = []
        for row in rows:
            pipelines.append({
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            })
        
        return {
            "status": "success",
            "pipelines": pipelines,
        }


@router.get("/{pipeline_id}")
async def get_pipeline(
    pipeline_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get a specific pipeline. Verifies ownership."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM pipelines WHERE id = ? AND user_id = ?",
            (pipeline_id, user["id"]),
        ).fetchone()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found or access denied",
            )
        
        # Parse pipeline JSON
        pipeline_data = json.loads(row["pipeline_json"])
        pipeline_data["id"] = row["id"]
        pipeline_data["name"] = row["name"]
        pipeline_data["description"] = row["description"]
        pipeline_data["status"] = row["status"]
        pipeline_data["created_at"] = row["created_at"]
        pipeline_data["updated_at"] = row["updated_at"]
        
        return {
            "status": "success",
            "pipeline": pipeline_data,
        }


@router.put("/{pipeline_id}")
async def update_pipeline(
    pipeline_id: str,
    pipeline_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update a pipeline. Verifies ownership."""
    with get_db() as conn:
        # Verify ownership
        existing = conn.execute(
            "SELECT id FROM pipelines WHERE id = ? AND user_id = ?",
            (pipeline_id, user["id"]),
        ).fetchone()
        
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found or access denied",
            )
        
        # Update pipeline
        name = pipeline_data.get("name", "Untitled Pipeline")
        description = pipeline_data.get("description")
        pipeline_json = json.dumps(pipeline_data)
        status_value = pipeline_data.get("status", "draft")
        
        conn.execute(
            """UPDATE pipelines 
               SET name = ?, description = ?, pipeline_json = ?, status = ?, updated_at = ?
               WHERE id = ? AND user_id = ?""",
            (name, description, pipeline_json, status_value, datetime.utcnow(), pipeline_id, user["id"]),
        )
    
    return {
        "status": "success",
        "message": "Pipeline updated successfully",
    }


@router.delete("/{pipeline_id}")
async def delete_pipeline(
    pipeline_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Delete a pipeline. Verifies ownership."""
    with get_db() as conn:
        # Verify ownership and delete
        result = conn.execute(
            "DELETE FROM pipelines WHERE id = ? AND user_id = ?",
            (pipeline_id, user["id"]),
        )
        
        if result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found or access denied",
            )
    
    return {
        "status": "success",
        "message": "Pipeline deleted successfully",
    }


@router.post("/{pipeline_id}/executions")
async def create_execution(
    pipeline_id: str,
    execution_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a pipeline execution record."""
    # Verify pipeline ownership
    with get_db() as conn:
        pipeline = conn.execute(
            "SELECT id FROM pipelines WHERE id = ? AND user_id = ?",
            (pipeline_id, user["id"]),
        ).fetchone()
        
        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found or access denied",
            )
        
        execution_id = str(uuid.uuid4())
        execution_log = json.dumps(execution_data.get("execution_log", []))
        status_value = execution_data.get("status", "running")
        
        conn.execute(
            """INSERT INTO pipeline_executions 
               (id, pipeline_id, user_id, status, started_at, execution_log)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                execution_id,
                pipeline_id,
                user["id"],
                status_value,
                datetime.utcnow(),
                execution_log,
            ),
        )
    
    return {
        "status": "success",
        "execution_id": execution_id,
    }


@router.get("/{pipeline_id}/executions")
async def list_executions(
    pipeline_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """List all executions for a pipeline. Verifies ownership."""
    with get_db() as conn:
        # Verify pipeline ownership
        pipeline = conn.execute(
            "SELECT id FROM pipelines WHERE id = ? AND user_id = ?",
            (pipeline_id, user["id"]),
        ).fetchone()
        
        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found or access denied",
            )
        
        rows = conn.execute(
            """SELECT * FROM pipeline_executions 
               WHERE pipeline_id = ? AND user_id = ?
               ORDER BY started_at DESC""",
            (pipeline_id, user["id"]),
        ).fetchall()
        
        executions = []
        for row in rows:
            execution = dict(row)
            # Parse execution log
            if execution.get("execution_log"):
                try:
                    execution["execution_log"] = json.loads(execution["execution_log"])
                except json.JSONDecodeError:
                    execution["execution_log"] = []
            executions.append(execution)
        
        return {
            "status": "success",
            "executions": executions,
        }

