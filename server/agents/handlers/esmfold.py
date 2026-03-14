#!/usr/bin/env python3
"""
ESMFold request handler for the server.
ESMFold uses ESM-2 language model — no MSA or templates required.
Blocking/synchronous flow: submit sequence, receive PDB immediately.
"""

import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

_server_dir = Path(__file__).resolve().parent.parent.parent
if str(_server_dir) not in sys.path:
    sys.path.insert(0, str(_server_dir))

try:
    from ...tools.nvidia.esmfold_client import ESMFoldClient
    from ...domain.storage.file_access import save_result_file
    from ...domain.storage.session_tracker import associate_file_with_session
except ImportError:
    from tools.nvidia.esmfold_client import ESMFoldClient
    from domain.storage.file_access import save_result_file
    from domain.storage.session_tracker import associate_file_with_session

logger = logging.getLogger(__name__)


class ESMFoldHandler:
    """Handles ESMFold structure prediction requests (blocking, no MSA needed)."""

    def __init__(self):
        self.client: Optional[ESMFoldClient] = None
        self.job_results: Dict[str, Dict[str, Any]] = {}

    def _get_client(self) -> ESMFoldClient:
        if self.client is None:
            try:
                self.client = ESMFoldClient()
            except ValueError as e:
                logger.error("ESMFold API configuration error: %s", e)
                raise ValueError(
                    "ESMFold requires NVCF_RUN_KEY or NVIDIA_API_KEY. "
                    "Get your key at https://build.nvidia.com/nvidia/esmfold"
                )
        return self.client

    async def process_predict_request(
        self,
        sequence: str,
        job_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process ESMFold prediction request (blocking).

        Args:
            sequence: Protein amino acid sequence (required, ≤400 residues)
            job_id: Client-provided job ID for storage and retrieval
            session_id: Chat session for file association
            user_id: User ID for storage isolation

        Returns:
            Dict with status, job_id, pdb_url, pdbContent, or error+code
        """
        job_id = job_id or str(uuid.uuid4())
        user_id = user_id or "system"

        # Early sequence validation before initializing client
        try:
            client = self._get_client()
        except ValueError as e:
            return {"status": "error", "error": str(e), "code": "API_KEY_MISSING"}

        is_valid, msg = client.validate_sequence(sequence)
        if not is_valid:
            code = "SEQUENCE_EMPTY" if not sequence or not sequence.strip() else "SEQUENCE_INVALID"
            if "short" in msg.lower():
                code = "SEQUENCE_TOO_SHORT"
            if "exceed" in msg.lower():
                code = "SEQUENCE_TOO_LONG"
            return {"status": "error", "error": msg, "code": code}

        try:
            result = await client.predict(sequence=sequence)
        except Exception as e:
            logger.exception("ESMFold predict raised")
            return {"status": "error", "error": str(e), "code": "API_ERROR"}

        if result.get("status") == "completed":
            data = result.get("data", {})
            pdb_content = client.extract_pdb_from_result(data)

            if not pdb_content:
                logger.warning(
                    "ESMFold: No PDB in response. Keys: %s",
                    list(data.keys()) if isinstance(data, dict) else type(data),
                )
                return {
                    "status": "error",
                    "error": "No PDB content in API response; unexpected response format",
                    "code": "API_ERROR",
                }

            filename = f"esmfold_{job_id}.pdb"
            stored_path = None

            try:
                stored_path = save_result_file(
                    user_id=user_id,
                    file_id=job_id,
                    file_type="esmfold",
                    filename=filename,
                    content=pdb_content.encode("utf-8"),
                    job_id=job_id,
                    metadata={"sequence_length": len(sequence.strip())},
                )
                try:
                    client.save_pdb_file(pdb_content, filename)
                except Exception as e:
                    logger.warning("Failed to save ESMFold result to esmfold_results folder: %s", e)
            except Exception as e:
                logger.error("Failed to save ESMFold result: %s", e)

            if session_id and user_id and stored_path:
                try:
                    associate_file_with_session(
                        session_id=str(session_id),
                        file_id=job_id,
                        user_id=user_id,
                        file_type="esmfold",
                        file_path=stored_path,
                        filename=filename,
                        size=len(pdb_content),
                        job_id=job_id,
                        metadata={"sequence_length": len(sequence.strip())},
                    )
                except Exception as e:
                    logger.warning("Failed to associate ESMFold file with session: %s", e)

            self.job_results[job_id] = {
                "pdbContent": pdb_content,
                "filename": filename,
                "stored_path": stored_path,
            }

            return {
                "status": "completed",
                "job_id": job_id,
                "pdb_url": f"/api/esmfold/result/{job_id}" if stored_path else None,
                "pdbContent": pdb_content,
                "message": "Structure predicted successfully",
            }

        if result.get("status") == "timeout":
            return {
                "status": "error",
                "error": result.get("error", "Prediction timed out"),
                "code": "TIMEOUT",
            }

        if result.get("status") == "validation_failed":
            return {"status": "error", "error": result.get("error", "Invalid sequence"), "code": "SEQUENCE_INVALID"}

        return {
            "status": "error",
            "error": result.get("error", "Prediction failed"),
            "code": "API_ERROR",
        }

    def get_result(self, job_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get cached result by job_id."""
        return self.job_results.get(job_id)


esmfold_handler = ESMFoldHandler()
