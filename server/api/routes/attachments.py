"""Attachments API endpoints for message-scoped file attachments."""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any, List, Optional
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

router = APIRouter(prefix="/api/conversations/{conversation_id}/messages", tags=["attachments"])


@router.post("/{message_id}/attachments")
async def create_attachment(
    conversation_id: str,
    message_id: str,
    attachment_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Add an attachment to a message. Verifies conversation and message ownership."""
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
        
        # Verify file exists and belongs to user
        file_id = attachment_data.get("file_id")
        if not file_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="file_id is required",
            )
        
        file = conn.execute(
            "SELECT id FROM user_files WHERE id = ? AND user_id = ?",
            (file_id, user_id),
        ).fetchone()
        
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found or access denied",
            )
        
        # Create attachment
        attachment_id = str(uuid.uuid4())
        file_name = attachment_data.get("file_name")
        file_type = attachment_data.get("file_type")
        file_size_kb = attachment_data.get("file_size_kb")
        
        conn.execute(
            """INSERT INTO attachments 
               (id, message_id, file_id, file_name, file_type, file_size_kb, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (attachment_id, message_id, file_id, file_name, file_type, file_size_kb, datetime.utcnow()),
        )
    
    return {
        "status": "success",
        "attachment_id": attachment_id,
        "message": "Attachment created successfully",
    }


@router.get("/{message_id}/attachments")
async def list_message_attachments(
    conversation_id: str,
    message_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """List all attachments for a message. Verifies conversation and message ownership."""
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
        
        # Get attachments
        rows = conn.execute(
            "SELECT * FROM attachments WHERE message_id = ? ORDER BY created_at ASC",
            (message_id,)
        ).fetchall()
        
        attachments = [dict(row) for row in rows]
    
    return {
        "status": "success",
        "attachments": attachments,
        "count": len(attachments),
    }


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(
    attachment_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Delete an attachment. Verifies ownership via message and conversation."""
    user_id = user["id"]
    
    with get_db() as conn:
        # Get attachment and verify ownership through message
        attachment = conn.execute(
            """SELECT a.*, m.conversation_id, m.session_id, m.user_id 
               FROM attachments a
               JOIN chat_messages m ON a.message_id = m.id
               WHERE a.id = ? AND m.user_id = ?""",
            (attachment_id, user_id),
        ).fetchone()
        
        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attachment not found or access denied",
            )
        
        # Delete attachment
        conn.execute(
            "DELETE FROM attachments WHERE id = ?",
            (attachment_id,)
        )
    
    return {
        "status": "success",
        "message": "Attachment deleted successfully",
    }
