"""Validation request handler for the server.

Integrates structure_validator to provide protein quality assessments
triggered via the chat agent system.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, Optional

# Ensure server directory is in Python path for imports
_server_dir = os.path.dirname(os.path.abspath(__file__))
if _server_dir not in sys.path:
    sys.path.insert(0, _server_dir)

try:
    # Try relative import first (when running as module)
    from ...tools.validation.structure_validator import validate_structure
    from ...domain.storage.file_access import get_user_file_path
except ImportError:
    # Fallback to absolute import (when running directly)
    from tools.validation.structure_validator import validate_structure
    from domain.storage.file_access import get_user_file_path

logger = logging.getLogger(__name__)


class ValidationHandler:
    """Handles structure validation requests from the chat agent system."""

    async def process_validation_request(
        self, input_text: str, context: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """
        Process a validation request.

        PDB source priority:
        1. Explicit file_id in context (user-uploaded file)
        2. current_pdb_content from the viewer
        3. Uploaded file context (attached file)

        Parameters
        ----------
        input_text : str
            The user's chat message.
        context : dict, optional
            Keys: current_pdb_content, uploaded_file_context, file_id,
            session_id, user_id.

        Returns
        -------
        dict
            On success: the validation report dict with action="validation_result".
            On error: {"action": "error", "error": "..."}.
        """
        context = context or {}
        pdb_content: Optional[str] = None

        # Priority 1: explicit file_id with user ownership check
        file_id = context.get("file_id")
        user_id = context.get("user_id")
        if file_id and user_id:
            try:
                file_path = get_user_file_path(file_id, user_id)
                pdb_content = file_path.read_text()
                logger.info("Validation: loaded PDB from file_id=%s", file_id)
            except Exception as exc:
                logger.warning("Failed to load file_id=%s: %s", file_id, exc)

        # Priority 2: current PDB content from the viewer
        if not pdb_content:
            pdb_content = context.get("current_pdb_content")
            if pdb_content:
                logger.info("Validation: using current_pdb_content from viewer")

        # Priority 3: uploaded file context
        if not pdb_content:
            uploaded = context.get("uploaded_file_context")
            if uploaded and isinstance(uploaded, dict):
                pdb_content = uploaded.get("pdb_content") or uploaded.get("content")
                if pdb_content:
                    logger.info("Validation: using uploaded_file_context")

        if not pdb_content:
            return {
                "action": "error",
                "error": (
                    "No structure available for validation. Please load a PDB "
                    "in the viewer, upload a file, or specify a PDB ID."
                ),
            }

        # Run validation
        try:
            report = validate_structure(pdb_content)
            result = report.to_dict()
            result["action"] = "validation_result"
            logger.info(
                "Validation complete: grade=%s score=%.1f",
                result.get("grade"),
                result.get("overall_score", 0),
            )
            return result
        except Exception as exc:
            logger.error("Validation failed: %s", exc)
            return {"action": "error", "error": str(exc)}


# Global handler instance
validation_handler = ValidationHandler()
