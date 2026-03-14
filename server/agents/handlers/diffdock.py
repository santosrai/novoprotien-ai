#!/usr/bin/env python3
"""
DiffDock request handler for the server.
Handles protein-ligand docking: open dialog and submit dock jobs (sync predict).
"""

import logging
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

_server_dir = Path(__file__).resolve().parent.parent.parent
if str(_server_dir) not in sys.path:
    sys.path.insert(0, str(_server_dir))

try:
    from ...tools.nvidia.diffdock_client import DiffDockClient
    from ...domain.storage.file_access import save_result_file
    from ...domain.storage.session_tracker import associate_file_with_session
    from ...domain.storage.pdb_storage import get_uploaded_pdb
except ImportError:
    from tools.nvidia.diffdock_client import DiffDockClient
    from domain.storage.file_access import save_result_file
    from domain.storage.session_tracker import associate_file_with_session
    from domain.storage.pdb_storage import get_uploaded_pdb

logger = logging.getLogger(__name__)


class DiffDockHandler:
    """Handles DiffDock protein-ligand docking requests."""

    def __init__(self):
        self.client: Optional[DiffDockClient] = None

    def _get_client(self) -> DiffDockClient:
        if self.client is None:
            try:
                self.client = DiffDockClient()
            except ValueError as e:
                logger.error("DiffDock API configuration error: %s", e)
                raise ValueError(
                    "DiffDock requires NVCF_RUN_KEY. "
                    "Get your key at https://build.nvidia.com/explore/discover"
                )
        return self.client

    async def process_dock_request(
        self,
        user_text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return action to open the DiffDock dialog (dialog-only flow)."""
        return {"action": "open_diffdock_dialog"}

    async def submit_dock_job(
        self,
        protein_file_id: Optional[str],
        protein_content: Optional[str],
        ligand_sdf_content: str,
        parameters: Dict[str, Any],
        user_id: str,
        session_id: Optional[str],
        job_id: Optional[str],
    ) -> Dict[str, Any]:
        """
        Submit a DiffDock job: resolve protein, call client, save result.
        Exactly one of protein_file_id or protein_content must be set.
        """
        if (protein_file_id and protein_content) or (not protein_file_id and not protein_content):
            return {
                "status": "error",
                "errorCode": "VALIDATION",
                "userMessage": "Provide exactly one: protein_file_id (uploaded PDB) or protein_content (PDB text).",
            }
        if not ligand_sdf_content or not ligand_sdf_content.strip():
            return {
                "status": "error",
                "errorCode": "VALIDATION",
                "userMessage": "Ligand SDF content is required.",
            }

        protein_pdb: str
        if protein_file_id:
            metadata = get_uploaded_pdb(protein_file_id, user_id=user_id)
            if not metadata:
                return {
                    "status": "error",
                    "errorCode": "FILE_NOT_FOUND",
                    "userMessage": "Uploaded protein file not found or access denied.",
                }
            path = metadata.get("absolute_path")
            if not path:
                return {
                    "status": "error",
                    "errorCode": "FILE_NOT_FOUND",
                    "userMessage": "Could not resolve protein file path.",
                }
            p = Path(path)
            try:
                protein_pdb = p.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                logger.warning("Failed to read protein file %s: %s", protein_file_id, e)
                return {
                    "status": "error",
                    "errorCode": "FILE_READ",
                    "userMessage": f"Could not read protein file: {e}",
                }
        else:
            protein_pdb = protein_content.strip()

        jid = job_id or str(uuid.uuid4())
        num_poses = int(parameters.get("num_poses", 10))
        time_divisions = int(parameters.get("time_divisions", 20))
        steps = int(parameters.get("steps", 18))
        save_trajectory = bool(parameters.get("save_trajectory", False))
        is_staged = bool(parameters.get("is_staged", True))

        try:
            client = self._get_client()
        except ValueError as e:
            return {
                "status": "error",
                "errorCode": "API_KEY_MISSING",
                "userMessage": str(e),
            }

        result = await client.predict(
            protein_content=protein_pdb,
            ligand_sdf_content=ligand_sdf_content,
            num_poses=num_poses,
            time_divisions=time_divisions,
            steps=steps,
            save_trajectory=save_trajectory,
            is_staged=is_staged,
        )

        if result.get("status") == "completed":
            data = result.get("data", {})
            pdb_content = client.extract_pdb_from_result(data)
            if not pdb_content:
                # API returned 200 but we could not extract a PDB (e.g. response shape changed)
                def _sample(v: Any, max_len: int = 120) -> str:
                    if isinstance(v, str):
                        return repr(v[:max_len] + ("..." if len(v) > max_len else ""))
                    if isinstance(v, (list, dict)):
                        return f"{type(v).__name__}(len={len(v)})"
                    return repr(v)

                sample = {k: _sample(v) for k, v in (data.items() if isinstance(data, dict) else [])}
                logger.warning(
                    "DiffDock returned success but no PDB could be extracted. Response sample: %s",
                    sample,
                )
                return {
                    "status": "error",
                    "errorCode": "API_ERROR",
                    "userMessage": (
                        "Docking completed but no structure was returned. "
                        "The API response format may differ from expectations. "
                        "Check server logs for response keys."
                    ),
                }
            stored_path = None
            if pdb_content:
                filename = f"diffdock_{jid}.pdb"
                try:
                    stored_path = save_result_file(
                        user_id=user_id,
                        file_id=jid,
                        file_type="diffdock",
                        filename=filename,
                        content=pdb_content.encode("utf-8"),
                        job_id=jid,
                        metadata={"num_poses": num_poses},
                    )
                except Exception as e:
                    logger.warning("Failed to save DiffDock result: %s", e)
                if session_id and stored_path:
                    try:
                        associate_file_with_session(
                            session_id=str(session_id),
                            file_id=jid,
                            user_id=user_id,
                            file_type="diffdock",
                            file_path=stored_path,
                            filename=filename,
                            size=len(pdb_content),
                            job_id=jid,
                            metadata={"num_poses": num_poses},
                        )
                    except Exception as e:
                        logger.warning("Failed to associate DiffDock file with session: %s", e)

            return {
                "status": "completed",
                "job_id": jid,
                "pdb_url": f"/api/diffdock/result/{jid}" if stored_path else None,
                "pdbContent": pdb_content,
                "message": "Docking completed successfully",
            }

        if result.get("status") == "timeout":
            return {
                "status": "error",
                "errorCode": "TIMEOUT",
                "userMessage": result.get("error", "Prediction timed out"),
            }

        api_error = result.get("error") or "Docking failed"
        logger.warning(
            "DiffDock job failed: status=%s error=%s",
            result.get("status"),
            api_error[:500] if isinstance(api_error, str) and len(api_error) > 500 else api_error,
        )
        return {
            "status": "error",
            "errorCode": "API_ERROR",
            "userMessage": api_error,
        }


diffdock_handler = DiffDockHandler()
