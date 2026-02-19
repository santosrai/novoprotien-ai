"""File access control and ownership verification utilities."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import HTTPException, status

try:
    # Try relative import first (when running as module)
    from ...database.db import get_db
except ImportError:
    # Fallback to absolute import (when running directly)
    from database.db import get_db

BASE_DIR = Path(__file__).parent.parent.parent


def _row_to_dict(row) -> Dict:
    """Convert sqlite3.Row to dict safely."""
    if isinstance(row, sqlite3.Row):
        return {key: row[key] for key in row.keys()}
    elif isinstance(row, dict):
        return row
    else:
        return dict(row)


def verify_file_ownership(file_id: str, user_id: str) -> bool:
    """Check if user owns the file."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM user_files WHERE id = ? AND user_id = ?",
            (file_id, user_id),
        ).fetchone()
        return row is not None


def get_user_file_path(file_id: str, user_id: str) -> Path:
    """Get file path with ownership check. Raises HTTPException if access denied."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT stored_path FROM user_files WHERE id = ? AND user_id = ?",
            (file_id, user_id),
        ).fetchone()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="File not found or access denied",
            )
        
        file_path = BASE_DIR / row["stored_path"]
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found on disk",
            )
        
        return file_path


def get_file_metadata(file_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
    """Get file metadata. If user_id provided, verifies ownership."""
    with get_db() as conn:
        query = "SELECT * FROM user_files WHERE id = ?"
        params = [file_id]
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        row = conn.execute(query, params).fetchone()
        if not row:
            return None
        
        # Convert Row to dict safely
        metadata = _row_to_dict(row)
        
        # Parse JSON metadata
        if metadata.get("metadata"):
            try:
                parsed_metadata = json.loads(metadata["metadata"])
                metadata.update(parsed_metadata)
            except json.JSONDecodeError:
                pass
        
        return metadata


def list_user_files(user_id: str, file_type: Optional[str] = None) -> List[Dict]:
    """List all files for a user, optionally filtered by type."""
    with get_db() as conn:
        query = "SELECT * FROM user_files WHERE user_id = ?"
        params = [user_id]
        
        if file_type:
            query += " AND file_type = ?"
            params.append(file_type)
        
        query += " ORDER BY created_at DESC"
        
        rows = conn.execute(query, params).fetchall()
        results = []
        
        for row in rows:
            # Convert Row to dict safely
            metadata = _row_to_dict(row)
            
            # Parse JSON metadata
            if metadata.get("metadata"):
                try:
                    parsed_metadata = json.loads(metadata["metadata"])
                    metadata.update(parsed_metadata)
                except json.JSONDecodeError:
                    pass
            
            # Check if file exists
            file_path = BASE_DIR / metadata["stored_path"]
            metadata["exists"] = file_path.exists()
            
            results.append(metadata)
        
        return results


def save_result_file(
    user_id: str,
    file_id: str,
    file_type: str,
    filename: str,
    content: bytes,
    job_id: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> str:
    """Save a result file (RFdiffusion, ProteinMPNN, AlphaFold) in user-scoped directory."""
    # Determine storage directory based on file type
    storage_dir = BASE_DIR / "storage" / user_id
    
    if file_type == "rfdiffusion":
        result_dir = storage_dir / "rfdiffusion_results"
    elif file_type == "proteinmpnn":
        result_dir = storage_dir / "proteinmpnn_results" / file_id
    elif file_type == "alphafold":
        result_dir = storage_dir / "alphafold_results"
    elif file_type == "openfold2":
        result_dir = storage_dir / "openfold2_results"
    elif file_type == "diffdock":
        result_dir = storage_dir / "diffdock_results"
    else:
        result_dir = storage_dir / "results"
    
    result_dir.mkdir(parents=True, exist_ok=True)
    
    # Save file
    if file_type == "proteinmpnn":
        # ProteinMPNN stores in subdirectory
        file_path = result_dir / filename
    else:
        file_path = result_dir / filename
    
    file_path.write_bytes(content)
    
    # Store metadata in database
    stored_path_rel = str(file_path.relative_to(BASE_DIR))
    metadata_json = json.dumps(metadata or {})
    
    with get_db() as conn:
        conn.execute(
            """INSERT INTO user_files 
               (id, user_id, file_type, original_filename, stored_path, size, metadata, job_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                file_id,
                user_id,
                file_type,
                filename,
                stored_path_rel,
                len(content),
                metadata_json,
                job_id,
            ),
        )
    
    return stored_path_rel

