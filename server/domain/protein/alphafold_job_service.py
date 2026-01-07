#!/usr/bin/env python3
"""
AlphaFold job persistence service.
Handles database operations for AlphaFold job tracking and recovery.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

try:
    from ...database.db import get_db
except ImportError:
    from database.db import get_db

logger = logging.getLogger(__name__)


class AlphaFoldJobService:
    """Service for managing AlphaFold job persistence"""
    
    @staticmethod
    def create_job(
        job_id: str,
        user_id: str,
        sequence: str,
        parameters: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> bool:
        """
        Create a new AlphaFold job in the database
        
        Args:
            job_id: Unique job identifier
            user_id: User who submitted the job
            sequence: Protein sequence
            parameters: Job parameters dictionary
            session_id: Optional chat session ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db() as conn:
                conn.execute(
                    """INSERT INTO alphafold_jobs 
                       (id, user_id, session_id, sequence, sequence_length, parameters, status, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, 'queued', CURRENT_TIMESTAMP)""",
                    (
                        job_id,
                        user_id,
                        session_id,
                        sequence,
                        len(sequence),
                        json.dumps(parameters),
                    ),
                )
            logger.info(f"Created AlphaFold job {job_id} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create AlphaFold job {job_id}: {e}")
            return False
    
    @staticmethod
    def update_job_status(
        job_id: str,
        status: str,
        progress: Optional[float] = None,
        progress_message: Optional[str] = None,
        nvidia_req_id: Optional[str] = None
    ) -> bool:
        """
        Update job status and progress
        
        Args:
            job_id: Job identifier
            status: New status (queued|running|completed|error|cancelled)
            progress: Optional progress percentage (0-100)
            progress_message: Optional status message
            nvidia_req_id: Optional NVIDIA API request ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            updates = []
            params = []
            
            updates.append("status = ?")
            params.append(status)
            
            updates.append("updated_at = CURRENT_TIMESTAMP")
            
            if progress is not None:
                updates.append("progress = ?")
                params.append(progress)
            
            if progress_message is not None:
                updates.append("progress_message = ?")
                params.append(progress_message)
            
            if nvidia_req_id is not None:
                updates.append("nvidia_req_id = ?")
                params.append(nvidia_req_id)
            
            if status == "running" and "started_at" not in [u.split()[0] for u in updates]:
                # Set started_at only if not already set
                updates.append("started_at = COALESCE(started_at, CURRENT_TIMESTAMP)")
            
            if status in ("completed", "error", "cancelled"):
                updates.append("completed_at = CURRENT_TIMESTAMP")
            
            params.append(job_id)
            
            with get_db() as conn:
                conn.execute(
                    f"UPDATE alphafold_jobs SET {', '.join(updates)} WHERE id = ?",
                    params,
                )
            return True
        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}")
            return False
    
    @staticmethod
    def get_job(job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve job by ID
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job dictionary or None if not found
        """
        try:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT * FROM alphafold_jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()
                
                if not row:
                    return None
                
                return {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "session_id": row["session_id"],
                    "sequence": row["sequence"],
                    "sequence_length": row["sequence_length"],
                    "parameters": json.loads(row["parameters"]) if row["parameters"] else {},
                    "status": row["status"],
                    "nvidia_req_id": row["nvidia_req_id"],
                    "result_filepath": row["result_filepath"],
                    "error_message": row["error_message"],
                    "progress": row["progress"],
                    "progress_message": row["progress_message"],
                    "created_at": row["created_at"],
                    "started_at": row["started_at"],
                    "completed_at": row["completed_at"],
                    "updated_at": row["updated_at"],
                }
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None
    
    @staticmethod
    def get_user_jobs(
        user_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get all jobs for a user
        
        Args:
            user_id: User identifier
            status: Optional status filter
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of job dictionaries
        """
        try:
            with get_db() as conn:
                query = "SELECT * FROM alphafold_jobs WHERE user_id = ?"
                params = [user_id]
                
                if status:
                    query += " AND status = ?"
                    params.append(status)
                
                query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                
                rows = conn.execute(query, params).fetchall()
                
                return [
                    {
                        "id": row["id"],
                        "user_id": row["user_id"],
                        "session_id": row["session_id"],
                        "sequence": row["sequence"],
                        "sequence_length": row["sequence_length"],
                        "parameters": json.loads(row["parameters"]) if row["parameters"] else {},
                        "status": row["status"],
                        "nvidia_req_id": row["nvidia_req_id"],
                        "result_filepath": row["result_filepath"],
                        "error_message": row["error_message"],
                        "progress": row["progress"],
                        "progress_message": row["progress_message"],
                        "created_at": row["created_at"],
                        "started_at": row["started_at"],
                        "completed_at": row["completed_at"],
                        "updated_at": row["updated_at"],
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get jobs for user {user_id}: {e}")
            return []
    
    @staticmethod
    def get_running_jobs() -> List[Dict[str, Any]]:
        """
        Get all running or queued jobs (for recovery)
        
        Returns:
            List of job dictionaries
        """
        try:
            with get_db() as conn:
                rows = conn.execute(
                    """SELECT * FROM alphafold_jobs 
                       WHERE status IN ('queued', 'running')
                       ORDER BY created_at ASC""",
                ).fetchall()
                
                return [
                    {
                        "id": row["id"],
                        "user_id": row["user_id"],
                        "session_id": row["session_id"],
                        "sequence": row["sequence"],
                        "sequence_length": row["sequence_length"],
                        "parameters": json.loads(row["parameters"]) if row["parameters"] else {},
                        "status": row["status"],
                        "nvidia_req_id": row["nvidia_req_id"],
                        "result_filepath": row["result_filepath"],
                        "error_message": row["error_message"],
                        "progress": row["progress"],
                        "progress_message": row["progress_message"],
                        "created_at": row["created_at"],
                        "started_at": row["started_at"],
                        "completed_at": row["completed_at"],
                        "updated_at": row["updated_at"],
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get running jobs: {e}")
            return []
    
    @staticmethod
    def mark_job_completed(
        job_id: str,
        result_filepath: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Mark job as completed with result filepath
        
        Args:
            job_id: Job identifier
            result_filepath: Path to result PDB file
            metadata: Optional additional metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db() as conn:
                conn.execute(
                    """UPDATE alphafold_jobs 
                       SET status = 'completed',
                           result_filepath = ?,
                           progress = 100.0,
                           completed_at = CURRENT_TIMESTAMP,
                           updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (result_filepath, job_id),
                )
            logger.info(f"Marked job {job_id} as completed")
            return True
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as completed: {e}")
            return False
    
    @staticmethod
    def mark_job_failed(job_id: str, error_message: str) -> bool:
        """
        Mark job as failed with error message
        
        Args:
            job_id: Job identifier
            error_message: Error details
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db() as conn:
                conn.execute(
                    """UPDATE alphafold_jobs 
                       SET status = 'error',
                           error_message = ?,
                           completed_at = CURRENT_TIMESTAMP,
                           updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (error_message, job_id),
                )
            logger.info(f"Marked job {job_id} as failed: {error_message}")
            return True
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as failed: {e}")
            return False
