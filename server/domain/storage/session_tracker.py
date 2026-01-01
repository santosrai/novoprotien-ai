"""Track PDB files associated with chat sessions."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from ...database.db import get_db


def create_chat_session(user_id: str, title: Optional[str] = None) -> str:
    """Create a new chat session and return its ID."""
    session_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            """INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, user_id, title, datetime.utcnow(), datetime.utcnow()),
        )
    return session_id


def get_user_sessions(user_id: str) -> List[Dict[str, any]]:
    """Get all chat sessions for a user."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM chat_sessions 
               WHERE user_id = ? 
               ORDER BY updated_at DESC""",
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def associate_file_with_session(
    session_id: str,
    file_id: str,
    user_id: str,
    file_type: str,
    file_path: str,
    filename: str,
    size: int,
    job_id: Optional[str] = None,
    metadata: Optional[Dict[str, any]] = None,
) -> None:
    """Associate a file with a session. Creates file entry if it doesn't exist."""
    with get_db() as conn:
        # Verify session belongs to user
        session = conn.execute(
            "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if not session:
            raise ValueError(f"Session {session_id} not found or access denied")
        
        # Check if file entry exists in user_files, create if not
        file_entry = conn.execute(
            "SELECT id FROM user_files WHERE id = ? AND user_id = ?",
            (file_id, user_id),
        ).fetchone()
        
        if not file_entry:
            # Create file entry
            metadata_json = json.dumps(metadata or {})
            conn.execute(
                """INSERT INTO user_files 
                   (id, user_id, file_type, original_filename, stored_path, size, metadata, job_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_id, user_id, file_type, filename, file_path, size, metadata_json, job_id),
            )
        
        # Associate file with session (ignore if already associated)
        try:
            conn.execute(
                """INSERT OR IGNORE INTO session_files (session_id, file_id, user_id, created_at)
                   VALUES (?, ?, ?, ?)""",
                (session_id, file_id, user_id, datetime.utcnow()),
            )
        except Exception:
            # Already associated, ignore
            pass


def get_session_files(session_id: str, user_id: Optional[str] = None) -> List[Dict[str, any]]:
    """Get all files associated with a session. If user_id provided, verifies ownership."""
    with get_db() as conn:
        query = """
            SELECT uf.*, sf.created_at as associated_at
            FROM session_files sf
            JOIN user_files uf ON sf.file_id = uf.id
            WHERE sf.session_id = ?
        """
        params = [session_id]
        
        if user_id:
            query += " AND sf.user_id = ?"
            params.append(user_id)
        
        rows = conn.execute(query, params).fetchall()
        
        results = []
        for row in rows:
            file_data = dict(row)
            # Parse JSON metadata
            if file_data.get("metadata"):
                try:
                    parsed_metadata = json.loads(file_data["metadata"])
                    file_data.update(parsed_metadata)
                except json.JSONDecodeError:
                    pass
            results.append(file_data)
        
        return results


def remove_file_from_session(session_id: str, file_id: str, user_id: str) -> None:
    """Remove a file association from a session. Verifies ownership."""
    with get_db() as conn:
        # Verify session belongs to user
        session = conn.execute(
            "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if not session:
            raise ValueError(f"Session {session_id} not found or access denied")
        
        # Remove association
        conn.execute(
            "DELETE FROM session_files WHERE session_id = ? AND file_id = ? AND user_id = ?",
            (session_id, file_id, user_id),
        )






