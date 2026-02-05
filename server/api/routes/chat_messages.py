"""Chat message management API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any, List, Optional
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

router = APIRouter(prefix="/api/chat/sessions/{session_id}/messages", tags=["chat_messages"])


@router.post("")
async def create_message(
    session_id: str,
    message_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a new message in a chat session/conversation. Verifies session ownership."""
    user_id = user["id"]
    
    with get_db() as conn:
        # Verify session/conversation ownership
        session = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        
        if not session:
            session = conn.execute(
                "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied",
            )
        
        # Create message
        message_id = str(uuid.uuid4())
        content = message_data.get("content", "")
        message_type = message_data.get("type", "user")
        role = message_data.get("role", message_type)
        metadata = message_data.get("metadata", {})
        
        # Determine sender_id: use provided sender_id, or default to user_id for human messages
        # For AI messages, sender_id should be the AI agent's user_id
        sender_id = message_data.get("sender_id")
        if not sender_id:
            if message_type == "ai" or role == "assistant":
                # Try to find AI agent user_id from conversation
                conv = conn.execute(
                    "SELECT ai_agent_id FROM conversations WHERE id = ?",
                    (session_id,)
                ).fetchone()
                sender_id = conv['ai_agent_id'] if conv and conv.get('ai_agent_id') else user_id
            else:
                sender_id = user_id
        
        # Use conversation_id if available, otherwise use session_id
        conversation_id = session_id  # Will be same for now
        
        conn.execute(
            """INSERT INTO chat_messages 
               (id, session_id, conversation_id, user_id, sender_id, content, message_type, role, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                message_id,
                session_id,
                conversation_id,
                user_id,
                sender_id,
                content,
                message_type,
                role,
                json.dumps(metadata) if metadata else None,
                datetime.utcnow(),
            ),
        )
        
        # Save 3D canvas data if provided
        three_d_canvas = message_data.get("threeDCanvas")
        if three_d_canvas:
            scene_data = three_d_canvas.get("sceneData", "")
            preview_url = three_d_canvas.get("previewUrl")
            
            if scene_data:
                canvas_id = str(uuid.uuid4())
                # If scene_data is a string (molstar code), wrap it in JSON
                if isinstance(scene_data, str):
                    scene_data_json = json.dumps({"molstar_code": scene_data})
                else:
                    scene_data_json = json.dumps(scene_data) if scene_data else json.dumps({})
                
                conn.execute(
                    """INSERT INTO three_d_canvases 
                       (id, message_id, conversation_id, scene_data, preview_url, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (canvas_id, message_id, conversation_id, scene_data_json, preview_url, datetime.utcnow(), datetime.utcnow()),
                )
        
        # Update session/conversation updated_at
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (datetime.utcnow(), session_id),
        )
        conn.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
            (datetime.utcnow(), session_id),
        )
    
    return {
        "status": "success",
        "message_id": message_id,
        "message": "Message created successfully",
    }


@router.get("")
async def list_messages(
    session_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> Dict[str, Any]:
    """List all messages in a chat session/conversation. Verifies session ownership.
    Returns messages with linked tools (3D canvas, pipeline, attachments)."""
    user_id = user["id"]
    
    with get_db() as conn:
        # Verify session/conversation ownership
        session = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        
        if not session:
            session = conn.execute(
                "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied",
            )
        
        # Get messages - check both session_id and conversation_id for compatibility
        query = """SELECT * FROM chat_messages 
                   WHERE (session_id = ? OR conversation_id = ?) AND user_id = ?
                   ORDER BY created_at ASC"""
        params = [session_id, session_id, user_id]
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
            if offset:
                query += " OFFSET ?"
                params.append(offset)
        
        rows = conn.execute(query, params).fetchall()
        
        messages = []
        for row in rows:
            msg = dict(row)
            message_id = msg['id']
            
            # Parse metadata JSON
            if msg.get("metadata"):
                try:
                    msg["metadata"] = json.loads(msg["metadata"])
                except json.JSONDecodeError:
                    msg["metadata"] = {}
            
            # Load linked 3D canvas
            canvas_row = conn.execute(
                "SELECT * FROM three_d_canvases WHERE message_id = ?",
                (message_id,)
            ).fetchone()
            if canvas_row:
                canvas = dict(canvas_row)
                try:
                    scene_data = json.loads(canvas['scene_data']) if canvas.get('scene_data') else {}
                    msg['threeDCanvas'] = {
                        'id': canvas['id'],
                        'sceneData': scene_data.get('molstar_code', canvas.get('scene_data', '')),
                        'previewUrl': canvas.get('preview_url'),
                    }
                except json.JSONDecodeError:
                    msg['threeDCanvas'] = {
                        'id': canvas['id'],
                        'sceneData': canvas.get('scene_data', ''),
                        'previewUrl': canvas.get('preview_url'),
                    }
            
            # Load linked pipeline
            pipeline_row = conn.execute(
                "SELECT id, name, pipeline_json, status FROM pipelines WHERE message_id = ?",
                (message_id,)
            ).fetchone()
            if pipeline_row:
                pipeline = dict(pipeline_row)
                try:
                    workflow_def = json.loads(pipeline['pipeline_json']) if pipeline.get('pipeline_json') else {}
                    msg['pipeline'] = {
                        'id': pipeline['id'],
                        'name': pipeline.get('name'),
                        'workflowDefinition': workflow_def,
                        'status': pipeline.get('status', 'draft'),
                    }
                except json.JSONDecodeError:
                    msg['pipeline'] = {
                        'id': pipeline['id'],
                        'name': pipeline.get('name'),
                        'workflowDefinition': {},
                        'status': pipeline.get('status', 'draft'),
                    }
            
            # Load linked attachments
            attachment_rows = conn.execute(
                "SELECT * FROM attachments WHERE message_id = ?",
                (message_id,)
            ).fetchall()
            if attachment_rows:
                msg['attachments'] = [
                    {
                        'id': att['id'],
                        'fileId': att['file_id'],
                        'fileName': att.get('file_name'),
                        'fileType': att.get('file_type'),
                        'fileSizeKb': att.get('file_size_kb'),
                    }
                    for att in attachment_rows
                ]
            
            messages.append(msg)
    
    return {
        "status": "success",
        "messages": messages,
        "count": len(messages),
    }


@router.get("/{message_id}")
async def get_message(
    session_id: str,
    message_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get a specific message. Verifies session ownership."""
    user_id = user["id"]
    
    with get_db() as conn:
        # Verify session ownership
        session = conn.execute(
            "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied",
            )
        
        # Get message - explicitly verify user_id for defense in depth
        # Check both session ownership AND message user_id (messages have user_id directly)
        row = conn.execute(
            "SELECT * FROM chat_messages WHERE id = ? AND session_id = ? AND user_id = ?",
            (message_id, session_id, user_id),
        ).fetchone()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )
        
        message = dict(row)
        # Parse metadata JSON
        if message.get("metadata"):
            try:
                message["metadata"] = json.loads(message["metadata"])
            except json.JSONDecodeError:
                message["metadata"] = {}
    
    return {
        "status": "success",
        "message": message,
    }


@router.put("/{message_id}")
async def update_message(
    session_id: str,
    message_id: str,
    message_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update a message. Verifies session ownership."""
    user_id = user["id"]
    
    with get_db() as conn:
        # Verify session ownership
        session = conn.execute(
            "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied",
            )
        
        # Verify message exists and belongs to session - explicitly check user_id
        # Check both session ownership AND message user_id (messages have user_id directly)
        message = conn.execute(
            "SELECT id FROM chat_messages WHERE id = ? AND session_id = ? AND user_id = ?",
            (message_id, session_id, user_id),
        ).fetchone()
        
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )
        
        # Update message
        updates = []
        params = []
        
        if "content" in message_data:
            updates.append("content = ?")
            params.append(message_data["content"])
        
        if "metadata" in message_data:
            updates.append("metadata = ?")
            params.append(json.dumps(message_data["metadata"]))
        
        if updates:
            params.append(message_id)
            params.append(session_id)
            params.append(user_id)  # Add user_id for explicit verification
            conn.execute(
                f"UPDATE chat_messages SET {', '.join(updates)} WHERE id = ? AND session_id = ? AND user_id = ?",
                params,
            )
            
            # Update session updated_at
            conn.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
                (datetime.utcnow(), session_id),
            )
    
    return {
        "status": "success",
        "message": "Message updated successfully",
    }


@router.delete("/{message_id}")
async def delete_message(
    session_id: str,
    message_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Delete a message. Verifies session ownership."""
    user_id = user["id"]
    
    with get_db() as conn:
        # Verify session ownership
        session = conn.execute(
            "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied",
            )
        
        # Delete message - explicitly verify user_id for defense in depth
        # Check both session ownership AND message user_id (messages have user_id directly)
        result = conn.execute(
            "DELETE FROM chat_messages WHERE id = ? AND session_id = ? AND user_id = ?",
            (message_id, session_id, user_id),
        )
        
        if result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )
        
        # Update session updated_at
        conn.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
            (datetime.utcnow(), session_id),
        )
    
    return {
        "status": "success",
        "message": "Message deleted successfully",
    }

