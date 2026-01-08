"""Three D Canvases API endpoints for message-scoped visualization code."""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any, Optional
import uuid
from datetime import datetime
import json

try:
    # Try relative import first (when running as module)
    from ...database.db import get_db
    from ..middleware.auth import get_current_user
except ImportError:
    # Fallback to absolute import (when running directly)
    from database.db import get_db
    from api.middleware.auth import get_current_user

router = APIRouter(prefix="/api/conversations/{conversation_id}/messages", tags=["three_d_canvases"])

# User-scoped router for getting canvases by user (not conversation)
user_router = APIRouter(prefix="/api/user", tags=["user_canvases"])


@router.post("/{message_id}/canvas")
async def create_canvas(
    conversation_id: str,
    message_id: str,
    canvas_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a 3D canvas linked to a message. Verifies conversation and message ownership."""
    user_id = user["id"]
    
    with get_db() as conn:
        # Verify conversation ownership
        conversation = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        
        if not conversation:
            # Fallback to chat_sessions for backward compatibility
            conversation = conn.execute(
                "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
                (conversation_id, user_id),
            ).fetchone()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access denied",
            )
        
        # Verify message exists and belongs to conversation
        message = conn.execute(
            """SELECT id FROM chat_messages 
               WHERE id = ? AND (conversation_id = ? OR session_id = ?) AND user_id = ?""",
            (message_id, conversation_id, conversation_id, user_id),
        ).fetchone()
        
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found or access denied",
            )
        
        # Check if canvas already exists for this message
        existing = conn.execute(
            "SELECT id FROM three_d_canvases WHERE message_id = ?",
            (message_id,)
        ).fetchone()
        
        scene_data = canvas_data.get("scene_data", "")
        preview_url = canvas_data.get("preview_url")
        
        # If scene_data is a string (molstar code), wrap it in JSON
        if isinstance(scene_data, str):
            scene_data_json = json.dumps({"molstar_code": scene_data})
        else:
            scene_data_json = json.dumps(scene_data) if scene_data else json.dumps({})
        
        if existing:
            # Update existing canvas
            canvas_id = existing['id']
            conn.execute(
                """UPDATE three_d_canvases 
                   SET scene_data = ?, preview_url = ?, updated_at = ?
                   WHERE message_id = ?""",
                (scene_data_json, preview_url, datetime.utcnow(), message_id),
            )
        else:
            # Create new canvas
            canvas_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO three_d_canvases 
                   (id, message_id, conversation_id, scene_data, preview_url, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (canvas_id, message_id, conversation_id, scene_data_json, preview_url, datetime.utcnow(), datetime.utcnow()),
            )
    
    return {
        "status": "success",
        "canvas_id": canvas_id,
        "message": "Canvas created successfully",
    }


@router.get("/{message_id}/canvas")
async def get_canvas(
    conversation_id: str,
    message_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get 3D canvas for a message. Verifies conversation and message ownership."""
    user_id = user["id"]
    
    with get_db() as conn:
        # Verify conversation ownership
        conversation = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        
        if not conversation:
            conversation = conn.execute(
                "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
                (conversation_id, user_id),
            ).fetchone()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access denied",
            )
        
        # Verify message exists
        message = conn.execute(
            """SELECT id FROM chat_messages 
               WHERE id = ? AND (conversation_id = ? OR session_id = ?) AND user_id = ?""",
            (message_id, conversation_id, conversation_id, user_id),
        ).fetchone()
        
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found or access denied",
            )
        
        # Get canvas
        canvas_row = conn.execute(
            "SELECT * FROM three_d_canvases WHERE message_id = ?",
            (message_id,)
        ).fetchone()
        
        if not canvas_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Canvas not found for this message",
            )
        
        canvas = dict(canvas_row)
        # Parse scene_data JSON
        try:
            scene_data = json.loads(canvas['scene_data']) if canvas.get('scene_data') else {}
        except json.JSONDecodeError:
            scene_data = {"molstar_code": canvas.get('scene_data', '')}
        
        return {
            "status": "success",
            "canvas": {
                "id": canvas['id'],
                "message_id": canvas['message_id'],
                "conversation_id": canvas['conversation_id'],
                "scene_data": scene_data,
                "preview_url": canvas.get('preview_url'),
                "version": canvas.get('version', 1),
                "created_at": canvas.get('created_at'),
                "updated_at": canvas.get('updated_at'),
            },
        }


@router.put("/{message_id}/canvas")
async def update_canvas(
    conversation_id: str,
    message_id: str,
    canvas_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update 3D canvas for a message. Verifies conversation and message ownership."""
    user_id = user["id"]
    
    with get_db() as conn:
        # Verify conversation ownership
        conversation = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        
        if not conversation:
            conversation = conn.execute(
                "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
                (conversation_id, user_id),
            ).fetchone()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access denied",
            )
        
        # Verify message exists
        message = conn.execute(
            """SELECT id FROM chat_messages 
               WHERE id = ? AND (conversation_id = ? OR session_id = ?) AND user_id = ?""",
            (message_id, conversation_id, conversation_id, user_id),
        ).fetchone()
        
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found or access denied",
            )
        
        # Get existing canvas
        existing = conn.execute(
            "SELECT id, version FROM three_d_canvases WHERE message_id = ?",
            (message_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Canvas not found. Use POST to create.",
            )
        
        # Update canvas
        updates = []
        params = []
        
        if "scene_data" in canvas_data:
            scene_data = canvas_data["scene_data"]
            if isinstance(scene_data, str):
                scene_data_json = json.dumps({"molstar_code": scene_data})
            else:
                scene_data_json = json.dumps(scene_data) if scene_data else json.dumps({})
            updates.append("scene_data = ?")
            params.append(scene_data_json)
        
        if "preview_url" in canvas_data:
            updates.append("preview_url = ?")
            params.append(canvas_data["preview_url"])
        
        if updates:
            # Increment version
            new_version = (existing['version'] or 1) + 1
            updates.append("version = ?")
            params.append(new_version)
            updates.append("updated_at = ?")
            params.append(datetime.utcnow())
            params.append(message_id)
            
            conn.execute(
                f"UPDATE three_d_canvases SET {', '.join(updates)} WHERE message_id = ?",
                params,
            )
    
    return {
        "status": "success",
        "message": "Canvas updated successfully",
    }


@router.get("/canvases")
async def list_conversation_canvases(
    conversation_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """List all 3D canvases in a conversation. Verifies conversation ownership."""
    user_id = user["id"]
    
    with get_db() as conn:
        # Verify conversation ownership
        conversation = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        
        if not conversation:
            conversation = conn.execute(
                "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
                (conversation_id, user_id),
            ).fetchone()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access denied",
            )
        
        # Get all canvases for this conversation
        rows = conn.execute(
            "SELECT * FROM three_d_canvases WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,)
        ).fetchall()
        
        canvases = []
        for row in rows:
            canvas = dict(row)
            try:
                scene_data = json.loads(canvas['scene_data']) if canvas.get('scene_data') else {}
            except json.JSONDecodeError:
                scene_data = {"molstar_code": canvas.get('scene_data', '')}
            
            canvases.append({
                "id": canvas['id'],
                "message_id": canvas['message_id'],
                "scene_data": scene_data,
                "preview_url": canvas.get('preview_url'),
                "version": canvas.get('version', 1),
                "created_at": canvas.get('created_at'),
                "updated_at": canvas.get('updated_at'),
            })
    
    return {
        "status": "success",
        "canvases": canvases,
        "count": len(canvases),
    }


@user_router.get("/canvases/latest")
async def get_user_latest_canvas(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get the latest canvas code for the current user across all messages."""
    user_id = user["id"]
    
    with get_db() as conn:
        # Query latest canvas by joining with messages to filter by user_id
        canvas_row = conn.execute(
            """SELECT c.*, m.id as message_id, m.conversation_id, m.session_id
               FROM three_d_canvases c
               JOIN chat_messages m ON c.message_id = m.id
               WHERE m.user_id = ?
               ORDER BY c.updated_at DESC
               LIMIT 1""",
            (user_id,)
        ).fetchone()
        
        if not canvas_row:
            return {
                "status": "success",
                "canvas": None,
                "message": "No canvas found for user",
            }
        
        canvas = dict(canvas_row)
        # Parse scene_data JSON
        try:
            scene_data = json.loads(canvas['scene_data']) if canvas.get('scene_data') else {}
        except json.JSONDecodeError:
            scene_data = {"molstar_code": canvas.get('scene_data', '')}
        
        # Extract molstar_code from scene_data
        molstar_code = scene_data.get('molstar_code', '') if isinstance(scene_data, dict) else str(scene_data)
        
        return {
            "status": "success",
            "canvas": {
                "id": canvas['id'],
                "message_id": canvas['message_id'],
                "conversation_id": canvas.get('conversation_id'),
                "session_id": canvas.get('session_id'),
                "scene_data": scene_data,
                "sceneData": molstar_code,  # For backward compatibility
                "preview_url": canvas.get('preview_url'),
                "version": canvas.get('version', 1),
                "created_at": canvas.get('created_at'),
                "updated_at": canvas.get('updated_at'),
            },
        }


@user_router.get("/canvases")
async def get_user_canvases(
    user: Dict[str, Any] = Depends(get_current_user),
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
) -> Dict[str, Any]:
    """Get all canvas codes for the current user across all messages."""
    user_id = user["id"]
    
    with get_db() as conn:
        # Query all canvases for this user, ordered by most recent
        rows = conn.execute(
            """SELECT c.*, m.id as message_id, m.conversation_id, m.session_id, m.created_at as message_created_at
               FROM three_d_canvases c
               JOIN chat_messages m ON c.message_id = m.id
               WHERE m.user_id = ?
               ORDER BY c.updated_at DESC
               LIMIT ? OFFSET ?""",
            (user_id, limit or 50, offset or 0)
        ).fetchall()
        
        canvases = []
        for row in rows:
            canvas = dict(row)
            try:
                scene_data = json.loads(canvas['scene_data']) if canvas.get('scene_data') else {}
            except json.JSONDecodeError:
                scene_data = {"molstar_code": canvas.get('scene_data', '')}
            
            molstar_code = scene_data.get('molstar_code', '') if isinstance(scene_data, dict) else str(scene_data)
            
            canvases.append({
                "id": canvas['id'],
                "message_id": canvas['message_id'],
                "conversation_id": canvas.get('conversation_id'),
                "session_id": canvas.get('session_id'),
                "scene_data": scene_data,
                "sceneData": molstar_code,  # For backward compatibility
                "preview_url": canvas.get('preview_url'),
                "version": canvas.get('version', 1),
                "created_at": canvas.get('created_at'),
                "updated_at": canvas.get('updated_at'),
                "message_created_at": canvas.get('message_created_at'),
            })
    
    return {
        "status": "success",
        "canvases": canvases,
        "count": len(canvases),
    }
