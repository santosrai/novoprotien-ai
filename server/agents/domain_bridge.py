"""Thin bridge to domain-layer async helpers used by the supervisor."""

from __future__ import annotations

from typing import Any, Dict, Optional


async def fetch_uniprot_sequence(accession: str) -> Optional[Dict[str, Any]]:
    """Fetch a UniProt entry and return its sequence + metadata."""
    try:
        from ..domain.protein.uniprot import fetch_uniprot_entry
    except ImportError:
        from domain.protein.uniprot import fetch_uniprot_entry

    try:
        return await fetch_uniprot_entry(accession)
    except Exception:
        return None
