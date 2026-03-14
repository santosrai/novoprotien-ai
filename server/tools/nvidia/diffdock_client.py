#!/usr/bin/env python3
"""
NVIDIA NIM API client for DiffDock protein-ligand docking.
Uploads protein (PDB) and ligand (SDF) as NVCF assets, then calls the DiffDock predict endpoint.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp
import ssl

try:
    import certifi
except ImportError:
    certifi = None

logger = logging.getLogger(__name__)

NVCF_ASSETS_URL = "https://api.nvcf.nvidia.com/v2/nvcf/assets"
DIFFDOCK_PREDICT_URL = "https://health.api.nvidia.com/v1/biology/mit/diffdock"


class DiffDockClient:
    """Client for NVIDIA DiffDock NIM API (protein-ligand docking via NVCF assets)."""

    def __init__(self, api_key: Optional[str] = None):
        raw_key = (
            api_key
            or os.getenv("NVCF_RUN_KEY")
            or os.getenv("NVIDIA_API_KEY")
            or ""
        )
        self.api_key = raw_key.strip()
        if not self.api_key:
            raise ValueError(
                "NVCF_RUN_KEY or NVIDIA_API_KEY environment variable required. "
                "Get your key at https://build.nvidia.com/explore/discover"
            )

        self.timeout = int(os.getenv("DIFFDOCK_TIMEOUT", "600"))  # 10 min default
        self.asset_timeout = int(os.getenv("DIFFDOCK_ASSET_TIMEOUT", "120"))

    def _auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "accept": "application/json",
        }

    async def _upload_asset(self, session: aiohttp.ClientSession, content: str) -> str:
        """
        Create an NVCF asset and upload content. Returns asset_id.
        """
        # 1. Create asset (get uploadUrl and assetId)
        payload = {"contentType": "text/plain", "description": "diffdock-file"}
        ssl_context = ssl.create_default_context()
        if certifi:
            try:
                ssl_context.load_verify_locations(certifi.where())
            except Exception:
                pass

        async with session.post(
            NVCF_ASSETS_URL,
            headers=self._auth_headers(),
            json=payload,
            ssl=ssl_context,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            upload_url = data.get("uploadUrl")
            asset_id = data.get("assetId")
            if not upload_url or not asset_id:
                raise ValueError(f"NVCF assets response missing uploadUrl/assetId: {data}")

        # 2. PUT content to uploadUrl
        s3_headers = {
            "x-amz-meta-nvcf-asset-description": "diffdock-file",
            "content-type": "text/plain",
        }
        async with session.put(
            upload_url,
            data=content.encode("utf-8"),
            headers=s3_headers,
            ssl=ssl_context,
            timeout=aiohttp.ClientTimeout(total=self.asset_timeout),
        ) as resp:
            resp.raise_for_status()

        return asset_id

    async def predict(
        self,
        protein_content: str,
        ligand_sdf_content: str,
        num_poses: int = 10,
        time_divisions: int = 20,
        steps: int = 18,
        save_trajectory: bool = False,
        is_staged: bool = True,
    ) -> Dict[str, Any]:
        """
        Upload protein and ligand as NVCF assets and run DiffDock prediction.

        Args:
            protein_content: PDB file content (string)
            ligand_sdf_content: SDF file content (string)
            num_poses: Number of poses to generate (default 10)
            time_divisions: Time divisions (default 20)
            steps: Diffusion steps (default 18)
            save_trajectory: Whether to save trajectory
            is_staged: Whether to use staged inference (default True)

        Returns:
            Dict with status, and on success: data (API response), or output_asset_ids / poses_pdb
            depending on API response shape.
        """
        if not protein_content or not protein_content.strip():
            return {"status": "validation_failed", "error": "Protein content is empty"}
        if not ligand_sdf_content or not ligand_sdf_content.strip():
            return {"status": "validation_failed", "error": "Ligand SDF content is empty"}

        ssl_context = ssl.create_default_context()
        if certifi:
            try:
                ssl_context.load_verify_locations(certifi.where())
            except Exception:
                pass

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Upload both assets
                protein_id = await self._upload_asset(session, protein_content)
                ligand_id = await self._upload_asset(session, ligand_sdf_content)

                # Call DiffDock
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "NVCF-INPUT-ASSET-REFERENCES": ",".join([protein_id, ligand_id]),
                }
                body = {
                    "ligand": ligand_id,
                    "ligand_file_type": "sdf",
                    "protein": protein_id,
                    "num_poses": num_poses,
                    "time_divisions": time_divisions,
                    "steps": steps,
                    "save_trajectory": save_trajectory,
                    "is_staged": is_staged,
                }

                logger.info(
                    "DiffDock request: protein_asset=%s ligand_asset=%s num_poses=%s",
                    protein_id, ligand_id, num_poses,
                )

                async with session.post(
                    DIFFDOCK_PREDICT_URL,
                    headers=headers,
                    json=body,
                    ssl=ssl_context,
                ) as response:
                    text = await response.text()
                    if response.status == 200:
                        try:
                            data = json.loads(text) if text.strip() else {}
                        except json.JSONDecodeError:
                            data = {"raw": text}
                        return {"status": "completed", "data": data}
                    else:
                        err_snippet = text[:1000] if len(text) > 1000 else text
                        err_msg = f"HTTP {response.status}: {err_snippet}" + ("..." if len(text) > 1000 else "")
                        logger.warning(
                            "DiffDock API HTTP %s: %s",
                            response.status,
                            err_snippet,
                        )
                        return {
                            "status": "request_failed",
                            "error": err_msg,
                            "http_status": response.status,
                        }
        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "error": "DiffDock prediction timed out",
            }
        except Exception as e:
            logger.exception("DiffDock API request failed")
            return {"status": "exception", "error": str(e)}

    def extract_pdb_from_result(self, result_data: Dict[str, Any]) -> Optional[str]:
        """Extract PDB content from API result for display/save.
        NVIDIA DiffDock may return visualizations_files (PDB), docked_ligand (SDF), pose_confidence.
        """
        try:
            if not isinstance(result_data, dict):
                return None
            # Direct string keys
            for key in ("pdb", "structure", "pdb_string", "pdb_content", "output"):
                val = result_data.get(key)
                if isinstance(val, str) and val.strip().startswith(("ATOM", "HEADER", "REMARK", "MODEL")):
                    return val
            # NVIDIA: visualizations_files can be PDB string or list of strings
            viz = result_data.get("visualizations_files")
            if isinstance(viz, str) and viz.strip().startswith(("ATOM", "HEADER", "REMARK", "MODEL")):
                return viz
            if isinstance(viz, list) and viz:
                first = viz[0]
                if isinstance(first, str) and first.strip().startswith(("ATOM", "HEADER", "REMARK", "MODEL")):
                    return first
            # poses array
            if "poses" in result_data and isinstance(result_data["poses"], list) and result_data["poses"]:
                first = result_data["poses"][0]
                if isinstance(first, str) and first.strip().startswith(("ATOM", "HEADER", "REMARK", "MODEL")):
                    return first
                if isinstance(first, dict) and "structure" in first:
                    return first["structure"]
            if "result" in result_data:
                return self.extract_pdb_from_result(result_data["result"])
            return None
        except Exception as e:
            logger.error("Error extracting PDB from DiffDock result: %s", e)
            return None
