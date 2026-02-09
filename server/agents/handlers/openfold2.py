#!/usr/bin/env python3
"""
OpenFold2 request handler for the server.
Handles structure prediction with optional MSA and template uploads.
Blocking/synchronous flow: submit and wait for result.
"""

import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure server directory is in Python path for imports
_server_dir = Path(__file__).resolve().parent.parent.parent
if str(_server_dir) not in sys.path:
    sys.path.insert(0, str(_server_dir))

try:
    from ...tools.nvidia.openfold2_client import OpenFold2Client
    from ...domain.storage.file_access import save_result_file
    from ...domain.storage.session_tracker import associate_file_with_session
except ImportError:
    from tools.nvidia.openfold2_client import OpenFold2Client
    from domain.storage.file_access import save_result_file
    from domain.storage.session_tracker import associate_file_with_session

logger = logging.getLogger(__name__)


def _parse_a3m_content(content: str) -> Optional[Dict[str, Any]]:
    """Parse a3m file content into OpenFold2 alignments format.
    Uses 'small_bfd' as key to match official API examples (alignments.small_bfd).
    """
    if not content or not content.strip():
        return None
    return {"small_bfd": {"a3m": {"alignment": content.strip(), "format": "a3m"}}}


def _is_hhr_content(content: str) -> bool:
    """Detect if content is HHR format (no longer supported by OpenFold2 v2.0+)."""
    if not content or not content.strip():
        return False
    s = content.strip()
    # HHR format: starts with "Query " or contains Probab/Hit markers
    return (
        s.startswith("Query ")
        or "Probab" in s[:800]
        or ("Hit" in s[:300] and "E-value" in s[:500])
    )


def _is_mmcif_content(content: str) -> bool:
    """Detect if content is mmCIF format (supported by OpenFold2 v2.0+)."""
    if not content or not content.strip():
        return False
    s = content.strip()
    return s.startswith("data_") or s.startswith("#") or s.startswith("loop_") or "_atom_site" in s[:500]


def _parse_mmcif_content(content: str, name: str = "user_template") -> Optional[Dict[str, Any]]:
    """Parse mmCIF template into OpenFold2 explicit_templates format (v2.0+)."""
    if not content or not content.strip():
        return None
    return {
        "name": name,
        "format": "mmcif",
        "structure": content.strip(),
        "source": "user_provided",
        "rank": -1,
    }


class OpenFold2Handler:
    """Handles OpenFold2 structure prediction requests (blocking)."""

    def __init__(self):
        self.client: Optional[OpenFold2Client] = None
        self.job_results: Dict[str, Dict[str, Any]] = {}

    def _get_client(self) -> OpenFold2Client:
        if self.client is None:
            try:
                self.client = OpenFold2Client()
            except ValueError as e:
                logger.error(f"OpenFold2 API configuration error: {e}")
                raise ValueError(
                    "OpenFold2 requires NVCF_RUN_KEY. "
                    "Get your key at https://build.nvidia.com/explore/discover"
                )
        return self.client

    async def process_predict_request(
        self,
        sequence: str,
        alignments: Optional[Dict[str, Any]] = None,
        alignments_raw: Optional[str] = None,
        templates: Optional[Any] = None,
        templates_raw: Optional[str] = None,
        relax_prediction: bool = False,
        job_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process structure prediction request (blocking).

        Args:
            sequence: Protein sequence (required)
            alignments: Pre-structured alignments dict (optional)
            alignments_raw: Raw a3m file content to parse (optional)
            templates: Pre-structured templates (optional)
            templates_raw: Raw hhr file content to parse (optional)
            relax_prediction: Whether to relax prediction
            job_id: Client-provided job ID for storage
            session_id: Chat session for association
            user_id: User ID for storage and session association

        Returns:
            Dict with status, job_id, pdb_url, pdbContent, or error
        """
        job_id = job_id or str(uuid.uuid4())
        user_id = user_id or "system"

        # Reject HHR templates early (OpenFold2 v2.0+ no longer supports them)
        if templates_raw and _is_hhr_content(templates_raw):
            return {
                "status": "error",
                "error": (
                    "OpenFold2 v2.0+ no longer supports HHR template format. "
                    "Please use mmCIF format (.cif) instead. "
                    "See https://docs.nvidia.com/nim/bionemo/openfold2/latest/migrating-from-hhr-to-explicit-templates.html"
                ),
                "code": "TEMPLATE_FORMAT_INVALID",
            }

        # Validate sequence
        client = self._get_client()
        is_valid, msg = client.validate_sequence(sequence)
        if not is_valid:
            return {
                "status": "error",
                "error": msg,
                "code": "SEQUENCE_EMPTY" if "empty" in msg.lower() else "SEQUENCE_INVALID",
            }
        if "1000" in msg:
            return {
                "status": "error",
                "error": msg,
                "code": "SEQUENCE_TOO_LONG",
            }

        # Build alignments from raw a3m if provided
        final_alignments = alignments
        if alignments_raw:
            parsed = _parse_a3m_content(alignments_raw)
            if parsed:
                final_alignments = parsed if not final_alignments else {**final_alignments, **parsed}

        # Build templates: OpenFold2 v2.0+ only supports mmCIF (explicit_templates)
        explicit_templates = None
        if templates_raw and _is_mmcif_content(templates_raw):
            t = _parse_mmcif_content(templates_raw)
            if t:
                explicit_templates = [t]

        try:
            result = await client.predict(
                sequence=sequence,
                alignments=final_alignments,
                explicit_templates=explicit_templates,
                relax_prediction=relax_prediction,
            )
        except ValueError as e:
            if "NVCF_RUN_KEY" in str(e) or "API key" in str(e).lower():
                return {
                    "status": "error",
                    "error": str(e),
                    "code": "API_KEY_MISSING",
                }
            raise

        if result.get("status") == "completed":
            data = result.get("data", {})
            pdb_content = client.extract_pdb_from_result(data)
            if not pdb_content:
                logger.warning(
                    "OpenFold2: No PDB in response. Keys: %s",
                    list(data.keys()) if isinstance(data, dict) else type(data),
                )
                return {
                    "status": "error",
                    "error": "No PDB content in API response; unexpected response format",
                    "code": "API_ERROR",
                }

            filename = f"openfold2_{job_id}.pdb"
            try:
                stored_path = save_result_file(
                    user_id=user_id,
                    file_id=job_id,
                    file_type="openfold2",
                    filename=filename,
                    content=pdb_content.encode("utf-8"),
                    job_id=job_id,
                    metadata={"sequence_length": len(sequence)},
                )
            except Exception as e:
                logger.error(f"Failed to save OpenFold2 result: {e}")
                # Still return pdbContent so frontend can use it
                stored_path = None

            if session_id and user_id and stored_path:
                try:
                    associate_file_with_session(
                        session_id=str(session_id),
                        file_id=job_id,
                        user_id=user_id,
                        file_type="openfold2",
                        file_path=stored_path,
                        filename=filename,
                        size=len(pdb_content),
                        job_id=job_id,
                        metadata={"sequence_length": len(sequence)},
                    )
                except Exception as e:
                    logger.warning(f"Failed to associate OpenFold2 file with session: {e}")

            self.job_results[job_id] = {
                "pdbContent": pdb_content,
                "filename": filename,
                "stored_path": stored_path,
            }

            return {
                "status": "completed",
                "job_id": job_id,
                "pdb_url": f"/api/openfold2/result/{job_id}" if stored_path else None,
                "pdbContent": pdb_content,
                "message": "Structure predicted successfully",
            }

        if result.get("status") == "timeout":
            return {
                "status": "error",
                "error": result.get("error", "Prediction timed out"),
                "code": "TIMEOUT",
            }

        return {
            "status": "error",
            "error": result.get("error", "Prediction failed"),
            "code": "API_ERROR",
        }

    def get_result(self, job_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get stored result by job_id. Optionally verify user_id."""
        return self.job_results.get(job_id)


openfold2_handler = OpenFold2Handler()
