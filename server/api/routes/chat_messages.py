"""Chat message management API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime
import json

from ...database.db import get_db
from ..middleware.auth import get_current_user

router = APIRouter(prefix="/api/chat/sessions/{session_id}/messages", tags=["chat_messages"])


@router.post("")
async def create_message(
    session_id: str,
    message_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a new message in a chat session. Verifies session ownership."""
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
        
        # Create message
        message_id = str(uuid.uuid4())
        content = message_data.get("content", "")
        message_type = message_data.get("type", "user")
        role = message_data.get("role", message_type)
        metadata = message_data.get("metadata", {})
        
        conn.execute(
            """INSERT INTO chat_messages 
               (id, session_id, user_id, content, message_type, role, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                message_id,
                session_id,
                user_id,
                content,
                message_type,
                role,
                json.dumps(metadata) if metadata else None,
                datetime.utcnow(),
            ),
        )
        
        # Update session updated_at
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
    """List all messages in a chat session. Verifies session ownership."""
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
        
        # Get messages
        query = "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC"
        params = [session_id]
        
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
            # Parse metadata JSON
            if msg.get("metadata"):
                try:
                    msg["metadata"] = json.loads(msg["metadata"])
                except json.JSONDecodeError:
                    msg["metadata"] = {}
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
        
        # Get message
        row = conn.execute(
            "SELECT * FROM chat_messages WHERE id = ? AND session_id = ?",
            (message_id, session_id),
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
        
        # Verify message exists and belongs to session
        message = conn.execute(
            "SELECT id FROM chat_messages WHERE id = ? AND session_id = ?",
            (message_id, session_id),
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
            conn.execute(
                f"UPDATE chat_messages SET {', '.join(updates)} WHERE id = ? AND session_id = ?",
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
        
        # Delete message
        result = conn.execute(
            "DELETE FROM chat_messages WHERE id = ? AND session_id = ?",
            (message_id, session_id),
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

