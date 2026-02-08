"""Pipeline persistence API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
import json
import uuid
from datetime import datetime

try:
    # Try relative import first (when running as module)
    from ...database.db import get_db
    from ..middleware.auth import get_current_user
except ImportError:
    # Fallback to absolute import (when running directly)
    from database.db import get_db
    from api.middleware.auth import get_current_user

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])


@router.post("")
async def create_pipeline(
    pipeline_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create or save a pipeline. Supports message_id and conversation_id for message-scoped pipelines."""
    pipeline_id = pipeline_data.get("id") or str(uuid.uuid4())
    name = pipeline_data.get("name", "Untitled Pipeline")
    description = pipeline_data.get("description")
    pipeline_json = json.dumps(pipeline_data)
    status_value = pipeline_data.get("status", "draft")
    message_id = pipeline_data.get("message_id")
    conversation_id = pipeline_data.get("conversation_id")
    
    with get_db() as conn:
        # Verify message and conversation ownership if provided
        if message_id:
            message = conn.execute(
                """SELECT id, conversation_id, session_id, user_id 
                   FROM chat_messages 
                   WHERE id = ? AND user_id = ?""",
                (message_id, user["id"]),
            ).fetchone()
            
            if not message:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Message not found or access denied",
                )
            
            # Use conversation_id from message if not provided
            if not conversation_id:
                message_dict = dict(message)
                conversation_id = message_dict.get('conversation_id') or message_dict.get('session_id')
        
        if conversation_id:
            # Verify conversation ownership
            conversation = conn.execute(
                "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
                (conversation_id, user["id"]),
            ).fetchone()
            
            if not conversation:
                conversation = conn.execute(
                    "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
                    (conversation_id, user["id"]),
                ).fetchone()
            
            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found or access denied",
                )
        
        # Check if pipeline exists and belongs to user
        existing = conn.execute(
            "SELECT id FROM pipelines WHERE id = ? AND user_id = ?",
            (pipeline_id, user["id"]),
        ).fetchone()
        
        if existing:
            # Update existing pipeline
            updates = ["name = ?", "description = ?", "pipeline_json = ?", "status = ?", "updated_at = ?"]
            params = [name, description, pipeline_json, status_value, datetime.utcnow()]
            
            if message_id is not None:
                updates.append("message_id = ?")
                params.append(message_id)
            if conversation_id is not None:
                updates.append("conversation_id = ?")
                params.append(conversation_id)
            
            params.extend([pipeline_id, user["id"]])
            conn.execute(
                f"""UPDATE pipelines 
                   SET {', '.join(updates)}
                   WHERE id = ? AND user_id = ?""",
                params,
            )
        else:
            # Create new pipeline
            conn.execute(
                """INSERT INTO pipelines 
                   (id, user_id, message_id, conversation_id, name, description, pipeline_json, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pipeline_id,
                    user["id"],
                    message_id,
                    conversation_id,
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
    conversation_id: Optional[str] = None,
    full: bool = False,
) -> Dict[str, Any]:
    """List all pipelines for the current user. Optionally filter by conversation_id.
    When full=true, returns full pipeline data (nodes, edges) in one request to avoid N+1 fetches."""
    with get_db() as conn:
        if conversation_id:
            # Verify conversation ownership
            conversation = conn.execute(
                "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
                (conversation_id, user["id"]),
            ).fetchone()
            
            if not conversation:
                conversation = conn.execute(
                    "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
                    (conversation_id, user["id"]),
                ).fetchone()
            
            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found or access denied",
                )
            
            query = """SELECT id, name, description, status, message_id, conversation_id, created_at, updated_at
                       FROM pipelines 
                       WHERE user_id = ? AND conversation_id = ?
                       ORDER BY updated_at DESC"""
            params = (user["id"], conversation_id)
        else:
            query = """SELECT id, name, description, status, message_id, conversation_id, created_at, updated_at
                       FROM pipelines 
                       WHERE user_id = ? 
                       ORDER BY updated_at DESC"""
            params = (user["id"],)
        
        if full:
            query = query.replace(
                "id, name, description, status, message_id, conversation_id, created_at, updated_at",
                "*",
            )
        
        rows = conn.execute(query, params).fetchall()
        
        pipelines = []
        for row in rows:
            row_dict = dict(row)
            if full and "pipeline_json" in row_dict:
                pipeline_data = json.loads(row_dict["pipeline_json"])
                pipeline_data["id"] = row_dict["id"]
                pipeline_data["name"] = row_dict.get("name")
                pipeline_data["description"] = row_dict.get("description")
                pipeline_data["status"] = row_dict.get("status", "draft")
                pipeline_data["created_at"] = row_dict.get("created_at")
                pipeline_data["updated_at"] = row_dict.get("updated_at")
                pipelines.append(pipeline_data)
            else:
                pipelines.append({
                    "id": row_dict["id"],
                    "name": row_dict.get("name"),
                    "description": row_dict.get("description"),
                    "status": row_dict.get("status", "draft"),
                    "message_id": row_dict.get("message_id"),
                    "conversation_id": row_dict.get("conversation_id"),
                    "created_at": row_dict.get("created_at"),
                    "updated_at": row_dict.get("updated_at"),
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
    """Update a pipeline. Verifies ownership. Supports updating message_id and conversation_id."""
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
        message_id = pipeline_data.get("message_id")
        conversation_id = pipeline_data.get("conversation_id")
        
        # Verify message and conversation ownership if provided
        if message_id:
            message = conn.execute(
                "SELECT id, user_id FROM chat_messages WHERE id = ? AND user_id = ?",
                (message_id, user["id"]),
            ).fetchone()
            
            if not message:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Message not found or access denied",
                )
        
        if conversation_id:
            conversation = conn.execute(
                "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
                (conversation_id, user["id"]),
            ).fetchone()
            
            if not conversation:
                conversation = conn.execute(
                    "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
                    (conversation_id, user["id"]),
                ).fetchone()
            
            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found or access denied",
                )
        
        updates = ["name = ?", "description = ?", "pipeline_json = ?", "status = ?", "updated_at = ?"]
        params = [name, description, pipeline_json, status_value, datetime.utcnow()]
        
        if message_id is not None:
            updates.append("message_id = ?")
            params.append(message_id)
        if conversation_id is not None:
            updates.append("conversation_id = ?")
            params.append(conversation_id)
        
        params.extend([pipeline_id, user["id"]])
        conn.execute(
            f"""UPDATE pipelines 
               SET {', '.join(updates)}
               WHERE id = ? AND user_id = ?""",
            params,
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

