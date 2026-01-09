"""Chat session management API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime

try:
    # Try relative import first (when running as module)
    from ...database.db import get_db
    from ...domain.storage.session_tracker import create_chat_session, get_user_sessions
    from ..middleware.auth import get_current_user
except ImportError:
    # Fallback to absolute import (when running directly)
    from database.db import get_db
    from domain.storage.session_tracker import create_chat_session, get_user_sessions
    from api.middleware.auth import get_current_user

router = APIRouter(prefix="/api/chat/sessions", tags=["chat_sessions"])


@router.post("")
async def create_session(
    session_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a new chat session/conversation."""
    # Allow frontend to specify session_id, or generate one
    session_id = session_data.get("id")
    title = session_data.get("title", "New Chat")
    ai_agent_id = session_data.get("ai_agent_id")  # Optional AI agent
    
    if session_id:
        # Check if session/conversation already exists
        with get_db() as conn:
            # Check conversations first (new table)
            existing_conv = conn.execute(
                "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
                (session_id, user["id"]),
            ).fetchone()
            
            # Check chat_sessions for backward compatibility
            existing_session = conn.execute(
                "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
                (session_id, user["id"]),
            ).fetchone()
            
            if existing_conv or existing_session:
                # Session already exists, return it
                return {
                    "status": "success",
                    "session_id": session_id,
                    "message": "Session already exists",
                }
            else:
                # Create conversation (new table)
                conn.execute(
                    """INSERT INTO conversations (id, user_id, ai_agent_id, title, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (session_id, user["id"], ai_agent_id, title, datetime.utcnow(), datetime.utcnow()),
                )
                # Also create in chat_sessions for backward compatibility
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
        # Also create in conversations table
        with get_db() as conn:
            conn.execute(
                """INSERT INTO conversations (id, user_id, ai_agent_id, title, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, user["id"], ai_agent_id, title, datetime.utcnow(), datetime.utcnow()),
            )
        return {
            "status": "success",
            "session_id": session_id,
            "message": "Session created successfully",
        }


@router.get("")
async def list_sessions(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """List all chat sessions/conversations for the current user."""
    # Try to get from conversations first (new table)
    with get_db() as conn:
        conversations = conn.execute(
            """SELECT id, user_id, ai_agent_id, title, created_at, updated_at 
               FROM conversations WHERE user_id = ? ORDER BY updated_at DESC""",
            (user["id"],)
        ).fetchall()
        
        if conversations:
            # Convert sqlite3.Row to dict for proper JSON serialization
            sessions = [dict(row) for row in conversations]
        else:
            # Fallback to chat_sessions for backward compatibility
            sessions = get_user_sessions(user["id"])
            # Ensure sessions from fallback are also dicts
            if sessions:
                sessions = [dict(s) if not isinstance(s, dict) else s for s in sessions]
    
    return {
        "status": "success",
        "sessions": sessions,
    }


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get a specific chat session/conversation. Verifies ownership."""
    with get_db() as conn:
        # Try conversations first (new table)
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
            (session_id, user["id"]),
        ).fetchone()
        
        # Fallback to chat_sessions for backward compatibility
        if not row:
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
    """Update a chat session/conversation. Verifies ownership."""
    with get_db() as conn:
        # Check if conversation exists (new table)
        existing_conv = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (session_id, user["id"]),
        ).fetchone()
        
        # Check chat_sessions for backward compatibility
        existing_session = conn.execute(
            "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user["id"]),
        ).fetchone()
        
        if not existing_conv and not existing_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied",
            )
        
        # Update conversation (new table)
        title = session_data.get("title")
        ai_agent_id = session_data.get("ai_agent_id")
        
        if existing_conv:
            updates = []
            params = []
            if title is not None:
                updates.append("title = ?")
                params.append(title)
            if ai_agent_id is not None:
                updates.append("ai_agent_id = ?")
                params.append(ai_agent_id)
            if updates:
                updates.append("updated_at = ?")
                params.append(datetime.utcnow())
                params.append(session_id)
                params.append(user["id"])
                conn.execute(
                    f"""UPDATE conversations 
                       SET {', '.join(updates)}
                       WHERE id = ? AND user_id = ?""",
                    params,
                )
        
        # Also update chat_sessions for backward compatibility
        if existing_session and title is not None:
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
    """Delete a chat session/conversation. Verifies ownership."""
    with get_db() as conn:
        # Delete from conversations (new table)
        result_conv = conn.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?",
            (session_id, user["id"]),
        )
        
        # Delete from chat_sessions for backward compatibility
        result_session = conn.execute(
            "DELETE FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user["id"]),
        )
        
        if result_conv.rowcount == 0 and result_session.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied",
            )
    
    return {
        "status": "success",
        "message": "Session deleted successfully",
    }


@router.get("/{session_id}/state")
async def get_session_state(
    session_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get session state (canvas/viewer state, model settings). Verifies ownership.
    
    Note: visualization_code is deprecated in favor of message-scoped three_d_canvases.
    This endpoint is kept for backward compatibility.
    """
    with get_db() as conn:
        # Verify session/conversation ownership
        session = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (session_id, user["id"]),
        ).fetchone()
        
        if not session:
            session = conn.execute(
                "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
                (session_id, user["id"]),
            ).fetchone()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied",
            )
        
        # Get session state (check if table exists first)
        state_row = None
        try:
            state_row = conn.execute(
                "SELECT * FROM session_state WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        except Exception as e:
            # Table doesn't exist or other error - return default state
            if "no such table" in str(e).lower():
                pass  # Table doesn't exist, will return default state
            else:
                raise
        
        if not state_row:
            # Return default state if none exists
            return {
                "status": "success",
                "state": {
                    "visualization_code": None,  # Deprecated - use message-scoped canvases
                    "viewer_visible": False,
                    "model_settings": None,
                },
            }
        
        state = dict(state_row)
        # Parse model_settings JSON
        if state.get("model_settings"):
            try:
                import json
                state["model_settings"] = json.loads(state["model_settings"])
            except json.JSONDecodeError:
                state["model_settings"] = None
        
        return {
            "status": "success",
            "state": {
                "visualization_code": state.get("visualization_code"),  # Deprecated
                "viewer_visible": bool(state.get("viewer_visible")),
                "model_settings": state.get("model_settings"),
            },
        }


@router.put("/{session_id}/state")
async def update_session_state(
    session_id: str,
    state_data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update session state (canvas/viewer state, model settings). Verifies ownership.
    
    Note: visualization_code is deprecated in favor of message-scoped three_d_canvases.
    This endpoint is kept for backward compatibility but logs a warning.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    with get_db() as conn:
        # Verify session/conversation ownership
        session = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (session_id, user["id"]),
        ).fetchone()
        
        if not session:
            session = conn.execute(
                "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
                (session_id, user["id"]),
            ).fetchone()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied",
            )
        
        # Prepare state data
        visualization_code = state_data.get("visualization_code")
        viewer_visible = state_data.get("viewer_visible", False)
        model_settings = state_data.get("model_settings")
        
        # Warn if visualization_code is being set (deprecated)
        if visualization_code:
            logger.warning(
                f"visualization_code set via deprecated session_state endpoint for session {session_id}. "
                "Consider using message-scoped three_d_canvases instead."
            )
        
        # Serialize model_settings to JSON
        import json
        model_settings_json = json.dumps(model_settings) if model_settings else None
        
        # Ensure session_state table exists
        try:
            conn.execute("SELECT 1 FROM session_state LIMIT 1").fetchone()
        except Exception as e:
            if "no such table" in str(e).lower():
                # Create session_state table if it doesn't exist
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS session_state (
                        session_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        visualization_code TEXT,
                        viewer_visible BOOLEAN DEFAULT 0,
                        model_settings TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_session_state_user_id ON session_state(user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_session_state_updated_at ON session_state(updated_at)")
        
        # Check if state exists
        try:
            existing = conn.execute(
                "SELECT session_id FROM session_state WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            
            if existing:
                # Update existing state
                conn.execute(
                    """UPDATE session_state 
                       SET visualization_code = ?, viewer_visible = ?, model_settings = ?, updated_at = ?
                       WHERE session_id = ?""",
                    (visualization_code, viewer_visible, model_settings_json, datetime.utcnow(), session_id),
                )
            else:
                # Create new state
                conn.execute(
                    """INSERT INTO session_state 
                       (session_id, user_id, visualization_code, viewer_visible, model_settings, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (session_id, user["id"], visualization_code, viewer_visible, model_settings_json, datetime.utcnow()),
                )
        except Exception as e:
            # If table still doesn't exist or other error, log and continue
            logger.warning(f"Failed to update session_state: {e}")
            # Don't raise - this is backward compatibility, not critical
    
    return {
        "status": "success",
        "message": "Session state updated successfully",
    }

