"""Alignment handler: fetches two PDB structures for client-side TM-align."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

# Ensure server directory is in Python path for imports
_server_dir = os.path.dirname(os.path.abspath(__file__))
if _server_dir not in sys.path:
    sys.path.insert(0, _server_dir)

try:
    from ...infrastructure.utils import log_line
    from ...domain.storage.pdb_storage import get_uploaded_pdb, list_uploaded_pdbs
except ImportError:
    from infrastructure.utils import log_line
    from domain.storage.pdb_storage import get_uploaded_pdb, list_uploaded_pdbs

logger = logging.getLogger(__name__)

# Regex patterns for protein identifiers
UNIPROT_RE = re.compile(r'\b([A-Z][0-9][A-Z0-9]{3}[0-9])\b')
PDB_RE = re.compile(r'\b(\d[A-Za-z0-9]{3})\b')


class AlignmentHandler:
    """Fetches two protein structures for frontend TM-align superposition."""

    async def _fetch_pdb_from_rcsb(self, pdb_id: str) -> str:
        """Fetch PDB content from RCSB."""
        url = f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text

    async def _fetch_pdb_from_alphafold(self, uniprot_id: str) -> str:
        """Fetch predicted structure from AlphaFold DB.

        First queries the API for the latest version, then downloads the PDB.
        Falls back to trying common versions if the API call fails.
        """
        uid = uniprot_id.upper()
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Try API first to get latest version
            try:
                api_resp = await client.get(f"https://alphafold.ebi.ac.uk/api/prediction/{uid}")
                if api_resp.status_code == 200:
                    data = api_resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        latest_version = data[0].get("latestVersion", 4)
                    else:
                        latest_version = 4
                else:
                    latest_version = 4
            except Exception:
                latest_version = 4

            # Try latest version first, then fall back
            versions_to_try = [latest_version]
            for v in [4, 3, 2]:
                if v not in versions_to_try:
                    versions_to_try.append(v)

            for version in versions_to_try:
                url = f"https://alphafold.ebi.ac.uk/files/AF-{uid}-F1-model_v{version}.pdb"
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.text

            # If all PDB attempts fail, try CIF with latest version
            url = f"https://alphafold.ebi.ac.uk/files/AF-{uid}-F1-model_v{latest_version}.cif"
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text

    async def _fetch_structure(
        self,
        protein_id: str,
        id_type: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch a single structure by ID and type.

        Returns dict with: pdbContent, label, source
        """
        try:
            if id_type == "pdb":
                pdb_content = await self._fetch_pdb_from_rcsb(protein_id)
                return {
                    "pdbContent": pdb_content,
                    "label": protein_id.upper(),
                    "source": "rcsb",
                }
            elif id_type == "uniprot":
                pdb_content = await self._fetch_pdb_from_alphafold(protein_id)
                return {
                    "pdbContent": pdb_content,
                    "label": protein_id.upper(),
                    "source": "alphafold_db",
                }
            elif id_type == "upload":
                # Try to find uploaded PDB
                pdb_data = get_uploaded_pdb(protein_id, user_id=user_id)
                if pdb_data and pdb_data.get("pdb_content"):
                    return {
                        "pdbContent": pdb_data["pdb_content"],
                        "label": pdb_data.get("filename", protein_id),
                        "source": "upload",
                    }
                raise ValueError(f"Uploaded PDB '{protein_id}' not found")
            elif id_type == "rfdiffusion":
                # Try to find RFdiffusion result
                base_dir = Path(__file__).parent.parent.parent
                rfdiffusion_dir = base_dir / "rfdiffusion_results"
                candidate = rfdiffusion_dir / f"rfdiffusion_{protein_id}.pdb"
                if candidate.exists():
                    return {
                        "pdbContent": candidate.read_text(),
                        "label": f"RFdiff_{protein_id[:8]}",
                        "source": "rfdiffusion",
                    }
                raise ValueError(f"RFdiffusion result '{protein_id}' not found")
            else:
                raise ValueError(f"Unknown identifier type: {id_type}")
        except httpx.HTTPStatusError as e:
            raise ValueError(
                f"Failed to fetch structure for {protein_id} ({id_type}): HTTP {e.response.status_code}"
            )

    def _detect_identifier_type(self, identifier: str) -> str:
        """Auto-detect whether an identifier is a PDB ID or UniProt accession."""
        identifier = identifier.strip()
        # UniProt pattern: starts with letter, then digit, then 3 alphanums, then digit
        if UNIPROT_RE.match(identifier.upper()):
            return "uniprot"
        # PDB pattern: starts with digit, then 3 alphanums
        if PDB_RE.match(identifier):
            return "pdb"
        # Default to uniprot for longer identifiers
        if len(identifier) >= 6:
            return "uniprot"
        return "pdb"

    def _parse_identifiers_from_text(self, text: str) -> list:
        """Extract protein identifiers from natural language text."""
        proteins = []

        # Try to find UniProt IDs first (more specific pattern)
        uniprot_matches = UNIPROT_RE.findall(text.upper())
        for match in uniprot_matches:
            proteins.append({"id": match, "type": "uniprot"})

        # If we didn't find 2 UniProt IDs, look for PDB IDs
        if len(proteins) < 2:
            pdb_matches = PDB_RE.findall(text)
            for match in pdb_matches:
                # Don't double-count if it was already matched as UniProt
                if match.upper() not in [p["id"] for p in proteins]:
                    proteins.append({"id": match.upper(), "type": "pdb"})

        return proteins[:2]  # Return at most 2

    async def process_request(
        self,
        input_text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process an alignment request.

        Parses two protein identifiers, fetches both structures,
        and returns them for client-side TM-align.
        """
        log_line("alignment:process_request", {"input": input_text[:200]})

        try:
            # First try to parse as JSON (from LLM agent response)
            parsed = None
            try:
                # The LLM might return JSON with the action
                json_match = re.search(r'\{[\s\S]*\}', input_text)
                if json_match:
                    parsed = json.loads(json_match.group())
            except (json.JSONDecodeError, AttributeError):
                pass

            proteins = []
            if parsed and "proteins" in parsed:
                proteins = parsed["proteins"]
            else:
                # Fall back to NLP extraction
                proteins = self._parse_identifiers_from_text(input_text)

            if len(proteins) < 2:
                return {
                    "action": "error",
                    "error": "Could not identify two proteins to compare. Please provide two PDB IDs (e.g., 1CBS, 4HHB) or UniProt accessions (e.g., Q6DG85, P11645).",
                }

            user_id = context.get("user_id") if context else None

            # Auto-detect types if not provided
            for p in proteins:
                if "type" not in p or p["type"] not in ("pdb", "uniprot", "upload", "rfdiffusion"):
                    p["type"] = self._detect_identifier_type(p["id"])

            # Fetch both structures
            structure1 = await self._fetch_structure(
                proteins[0]["id"], proteins[0]["type"], user_id
            )
            structure2 = await self._fetch_structure(
                proteins[1]["id"], proteins[1]["type"], user_id
            )

            log_line("alignment:structures_fetched", {
                "s1": structure1["label"],
                "s2": structure2["label"],
                "s1_source": structure1["source"],
                "s2_source": structure2["source"],
                "s1_size": len(structure1["pdbContent"]),
                "s2_size": len(structure2["pdbContent"]),
            })

            return {
                "action": "show_alignment",
                "alignmentResult": {
                    "structure1": {
                        "pdbContent": structure1["pdbContent"],
                        "label": structure1["label"],
                    },
                    "structure2": {
                        "pdbContent": structure2["pdbContent"],
                        "label": structure2["label"],
                    },
                },
                "text": f"Comparing {structure1['label']} and {structure2['label']} structures. Click 'Compare in 3D' to overlay them with TM-align superposition.",
            }

        except ValueError as e:
            log_line("alignment:error", {"error": str(e)})
            return {"action": "error", "error": str(e)}
        except Exception as e:
            log_line("alignment:unexpected_error", {"error": str(e)})
            return {"action": "error", "error": f"Alignment failed: {str(e)}"}


# Singleton instance
alignment_handler = AlignmentHandler()
