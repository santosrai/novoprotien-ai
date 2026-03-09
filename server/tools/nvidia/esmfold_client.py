#!/usr/bin/env python3
"""
NVIDIA NIM API client for ESMFold protein structure prediction.
ESMFold uses ESM-2 language model — no MSA or templates required.
Blocking/synchronous: submit sequence, receive PDB immediately.
"""

import asyncio
import logging
import os
import ssl
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import aiohttp

try:
    import certifi
except ImportError:
    certifi = None

logger = logging.getLogger(__name__)

# Valid amino acid single-letter codes
VALID_AA = set("ACDEFGHIKLMNPQRSTVWY")

# ESMFold NIM limits
MAX_SEQUENCE_LENGTH = 400
MIN_SEQUENCE_LENGTH = 6


class ESMFoldClient:
    """Client for NVIDIA ESMFold NIM API (synchronous prediction, no MSA needed)."""

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
                "Get your key at https://build.nvidia.com/nvidia/esmfold"
            )

        self.base_url = (
            os.getenv("ESMFOLD_URL")
            or "https://health.api.nvidia.com/v1/biology/nvidia/esmfold"
        )
        self.timeout = int(os.getenv("ESMFOLD_TIMEOUT", "120"))  # 2 min default

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    def validate_sequence(self, sequence: str) -> Tuple[bool, str]:
        """Validate protein sequence. ESMFold NIM: 6–400 residues, standard AA only."""
        if not sequence or not sequence.strip():
            return False, "Sequence cannot be empty"

        clean = "".join(sequence.split()).upper()

        invalid = set(clean) - VALID_AA
        if invalid:
            return False, f"Invalid amino acids: {', '.join(sorted(invalid))}"

        if len(clean) < MIN_SEQUENCE_LENGTH:
            return False, f"Sequence too short ({len(clean)} residues). Minimum: {MIN_SEQUENCE_LENGTH}"

        if len(clean) > MAX_SEQUENCE_LENGTH:
            return (
                False,
                f"Sequence exceeds {MAX_SEQUENCE_LENGTH} residues ({len(clean)}). "
                "ESMFold NIM supports up to 400 residues. Use AlphaFold2 or OpenFold2 for longer sequences.",
            )

        return True, clean

    def build_payload(self, sequence: str) -> Dict[str, Any]:
        """Build ESMFold request payload."""
        return {"sequence": sequence}

    def extract_pdb_from_result(self, result_data: Dict[str, Any]) -> Optional[str]:
        """Extract PDB string from ESMFold API response.
        NVIDIA ESMFold returns: {"pdbs": ["ATOM ...\n..."]}
        """
        try:
            if not isinstance(result_data, dict):
                return None

            # Primary: NVIDIA ESMFold response format
            pdbs = result_data.get("pdbs")
            if pdbs and isinstance(pdbs, list) and pdbs[0]:
                first = pdbs[0]
                if isinstance(first, str) and first.strip().startswith(("ATOM", "HEADER", "REMARK", "MODEL")):
                    return first

            # Fallback: common PDB key names
            for key in ("pdb", "structure", "pdb_string", "pdb_content"):
                val = result_data.get(key)
                if isinstance(val, str) and val.strip().startswith(("ATOM", "HEADER", "REMARK")):
                    return val

            logger.warning("Could not extract PDB from ESMFold result keys: %s", list(result_data.keys()))
            return None
        except Exception as e:
            logger.error("Error extracting PDB from ESMFold result: %s", e)
            return None

    async def predict(self, sequence: str) -> Dict[str, Any]:
        """
        Submit synchronous structure prediction to ESMFold NIM.

        Args:
            sequence: Validated amino acid sequence (≤400 residues)

        Returns:
            Dict with status ("completed" | "timeout" | "request_failed" | "exception")
            and data (containing PDB) or error message.
        """
        is_valid, result = self.validate_sequence(sequence)
        if not is_valid:
            return {"status": "validation_failed", "error": result}

        clean_sequence = result
        payload = self.build_payload(clean_sequence)

        logger.info("ESMFold request: url=%s sequence_len=%s", self.base_url, len(clean_sequence))

        try:
            ssl_context = ssl.create_default_context()
            if certifi:
                try:
                    ssl_context.load_verify_locations(certifi.where())
                except Exception:
                    pass

            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload,
                    ssl=ssl_context,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {"status": "completed", "data": data}
                    else:
                        text = await response.text()
                        logger.warning("ESMFold API HTTP %s: %s", response.status, text[:500])
                        return {
                            "status": "request_failed",
                            "error": f"HTTP {response.status}: {text[:500]}" + ("..." if len(text) > 500 else ""),
                            "http_status": response.status,
                        }
        except asyncio.TimeoutError:
            return {"status": "timeout", "error": "Prediction timed out. Try a shorter sequence."}
        except Exception as e:
            logger.exception("ESMFold API request failed")
            return {"status": "exception", "error": str(e)}

    def save_pdb_file(self, pdb_content: str, filename: str) -> str:
        """Save PDB content to esmfold_results folder."""
        try:
            base_dir = Path(__file__).parent
            results_dir = base_dir / "esmfold_results"
            results_dir.mkdir(exist_ok=True)
            filepath = results_dir / filename
            filepath.write_text(pdb_content, encoding="utf-8")
            return str(filepath.relative_to(base_dir))
        except Exception as e:
            logger.error("Error saving ESMFold PDB file: %s", e)
            raise
