"""Chat session management API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime

from ...database.db import get_db
from ...domain.storage.session_tracker import create_chat_session, get_user_sessions
from ..middleware.auth import get_current_user

router = APIRouter(prefix="/api/chat/sessions", tags=["chat_sessions"])


@router.post("")
async def create_session(
    session_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a new chat session."""
    # Allow frontend to specify session_id, or generate one
    session_id = session_data.get("id")
    title = session_data.get("title", "New Chat")
    
    if session_id:
        # Check if session already exists
        with get_db() as conn:
            existing = conn.execute(
                "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
                (session_id, user["id"]),
            ).fetchone()
            
            if existing:
                # Session already exists, return it
                return {
                    "status": "success",
                    "session_id": session_id,
                    "message": "Session already exists",
                }
            else:
                # Create session with specified ID
                with get_db() as conn:
                    conn.execute(
                        """INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (session_id, user["id"], title, datetime.utcnow(), datetime.utcnow()),
                    )
                return {
                    "status": "success",
                    "session_id": session_id,
                    "message": "Session created successfully",
                }
    else:
        # Generate new session ID
        session_id = create_chat_session(user["id"], title)
        return {
            "status": "success",
            "session_id": session_id,
            "message": "Session created successfully",
        }


@router.get("")
async def list_sessions(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """List all chat sessions for the current user."""
    sessions = get_user_sessions(user["id"])
    
    return {
        "status": "success",
        "sessions": sessions,
    }


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get a specific chat session. Verifies ownership."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user["id"]),
        ).fetchone()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied",
            )
        
        return {
            "status": "success",
            "session": dict(row),
        }


@router.put("/{session_id}")
async def update_session(
    session_id: str,
    session_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update a chat session. Verifies ownership."""
    with get_db() as conn:
        # Verify ownership
        existing = conn.execute(
            "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user["id"]),
        ).fetchone()
        
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied",
            )
        
        # Update session
        title = session_data.get("title")
        conn.execute(
            """UPDATE chat_sessions 
               SET title = ?, updated_at = ?
               WHERE id = ? AND user_id = ?""",
            (title, datetime.utcnow(), session_id, user["id"]),
        )
    
    return {
        "status": "success",
        "message": "Session updated successfully",
    }


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Delete a chat session. Verifies ownership."""
    with get_db() as conn:
        # Verify ownership and delete (CASCADE will handle session_files)
        result = conn.execute(
            "DELETE FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user["id"]),
        )
        
        if result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied",
            )
    
    return {
        "status": "success",
        "message": "Session deleted successfully",
    }

