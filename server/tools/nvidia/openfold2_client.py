#!/usr/bin/env python3
"""
NVIDIA NIM API client for OpenFold2 protein structure prediction.
Handles synchronous prediction requests with optional MSA and template inputs.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional, Tuple

import aiohttp
import ssl

try:
    import certifi
except ImportError:
    certifi = None

logger = logging.getLogger(__name__)

# Valid amino acid single-letter codes
VALID_AA = set("ACDEFGHIKLMNPQRSTVWY")


class OpenFold2Client:
    """Client for NVIDIA OpenFold2 NIM API (synchronous prediction)"""

    def __init__(self, api_key: Optional[str] = None):
        # Support both NVCF_RUN_KEY (build.nvidia.com) and NVIDIA_API_KEY (official examples)
        raw_key = (
            api_key
            or os.getenv("NVCF_RUN_KEY")
            or os.getenv("NVIDIA_API_KEY")
            or ""
        )
        self.api_key = raw_key.strip()
        if not self.api_key:
            raise ValueError(
                "NVCF_RUN_KEY environment variable or api_key parameter required. "
                "Get your key at https://build.nvidia.com/explore/discover"
            )

        # Hosted API endpoint - same pattern as AlphaFold2/RFdiffusion
        self.base_url = (
            os.getenv("OPENFOLD2_URL")
            or "https://health.api.nvidia.com/v1/biology/openfold/openfold2/predict-structure-from-msa-and-template"
        )
        self.timeout = int(os.getenv("OPENFOLD2_TIMEOUT", "600"))  # 10 min default

        self.headers = {
            "content-type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "NVCF-POLL-SECONDS": str(min(300, self.timeout)),  # Long-poll hint for hosted API
        }

    def validate_sequence(self, sequence: str) -> Tuple[bool, str]:
        """Validate protein sequence format and length (OpenFold2: ≤1000 chars)."""
        if not sequence:
            return False, "Sequence cannot be empty"

        clean_seq = "".join(sequence.split()).upper()

        invalid_chars = set(clean_seq) - VALID_AA
        if invalid_chars:
            return False, f"Invalid amino acids found: {', '.join(sorted(invalid_chars))}"

        if len(clean_seq) < 20:
            return False, f"Sequence too short ({len(clean_seq)} residues). Minimum: 20"
        if len(clean_seq) > 1000:
            return False, (
                f"Sequence exceeds 1000 residues ({len(clean_seq)}). "
                "Use AlphaFold2 for longer sequences."
            )

        return True, clean_seq

    def build_payload(
        self,
        sequence: str,
        alignments: Optional[Dict[str, Any]] = None,
        templates: Optional[Any] = None,
        relax_prediction: bool = False,
    ) -> Dict[str, Any]:
        """Build request payload for OpenFold2 API."""
        payload: Dict[str, Any] = {
            "sequence": sequence,
            "selected_models": [1, 2, 3, 4, 5],  # Default: all 5 models
            "relax_prediction": relax_prediction,
        }
        if alignments:
            payload["alignments"] = alignments
        if templates:
            payload["templates"] = templates
        return payload

    async def predict(
        self,
        sequence: str,
        alignments: Optional[Dict[str, Any]] = None,
        templates: Optional[Any] = None,
        relax_prediction: bool = False,
    ) -> Dict[str, Any]:
        """
        Submit synchronous structure prediction request to OpenFold2 NIM.

        Args:
            sequence: Protein amino acid sequence (≤1000 chars)
            alignments: Optional MSA in format { "uniref90": { "a3m": { "alignment": "...", "format": "a3m" } } }
            templates: Optional template data in hhr format
            relax_prediction: Whether to apply relaxation step

        Returns:
            Dict with status, data (containing PDB), or error
        """
        is_valid, result = self.validate_sequence(sequence)
        if not is_valid:
            return {"status": "validation_failed", "error": result}

        clean_sequence = result
        payload = self.build_payload(
            clean_sequence,
            alignments=alignments,
            templates=templates,
            relax_prediction=relax_prediction,
        )

        logger.info(
            "OpenFold2 request: url=%s sequence_len=%s has_alignments=%s has_templates=%s",
            self.base_url,
            len(clean_sequence),
            bool(alignments),
            bool(templates),
        )

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
                        logger.warning(
                            "OpenFold2 API HTTP %s: %s",
                            response.status,
                            text[:500] if len(text) > 500 else text,
                        )
                        return {
                            "status": "request_failed",
                            "error": f"HTTP {response.status}: {text[:500]}" + ("..." if len(text) > 500 else ""),
                            "http_status": response.status,
                        }
        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "error": "Prediction timed out; try a shorter sequence",
            }
        except Exception as e:
            logger.exception("OpenFold2 API request failed")
            return {"status": "exception", "error": str(e)}

    def extract_pdb_from_result(self, result_data: Dict[str, Any]) -> Optional[str]:
        """Extract PDB content from API result.
        OpenFold2 hosted API returns: structures_in_ranked_order: [{structure: "..."}]
        """
        try:
            if not isinstance(result_data, dict):
                return None

            # OpenFold2 hosted API: structures_in_ranked_order (list of {structure: pdb_string})
            if "structures_in_ranked_order" in result_data:
                structs = result_data["structures_in_ranked_order"]
                if structs and isinstance(structs[0], dict):
                    val = structs[0].get("structure")
                    if isinstance(val, str) and val.strip():
                        return val
                if structs and isinstance(structs[0], str):
                    return structs[0]

            # Try common response shapes (OpenFold2 / AlphaFold-style)
            for key in ("pdb", "structure", "pdb_string", "pdb_content", "unrelaxed_pdb"):
                val = result_data.get(key)
                if isinstance(val, str) and val.strip().startswith(("ATOM", "HEADER", "REMARK")):
                    return val

            if "prediction" in result_data and isinstance(result_data["prediction"], dict):
                out = self.extract_pdb_from_result(result_data["prediction"])
                if out:
                    return out
            if "result" in result_data:
                out = self.extract_pdb_from_result(result_data["result"])
                if out:
                    return out
            # OpenFold2 returns list of predictions, ordered by confidence
            if "predictions" in result_data:
                preds = result_data["predictions"]
                if preds:
                    first = preds[0]
                    if isinstance(first, str) and first.strip().startswith(("ATOM", "HEADER", "REMARK")):
                        return first
                    if isinstance(first, dict):
                        out = self.extract_pdb_from_result(first)
                        if out:
                            return out

            logger.warning(f"Could not extract PDB from result keys: {list(result_data.keys())}")
            return None
        except Exception as e:
            logger.error(f"Error extracting PDB from result: {e}")
            return None
