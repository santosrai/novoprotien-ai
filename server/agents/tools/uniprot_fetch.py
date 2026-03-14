"""LangChain tool: fetch a single UniProt entry by accession."""

from __future__ import annotations

import json

try:
    from langchain_core.tools import tool
except ImportError:
    tool = None


def get_uniprot_fetch_tool():
    """Return a LangChain tool that fetches a UniProt entry (async)."""
    if tool is None:
        raise RuntimeError("langchain_core.tools is required")

    try:
        from ...domain.protein.uniprot import fetch_uniprot_entry as _fetch
    except ImportError:
        from domain.protein.uniprot import fetch_uniprot_entry as _fetch

    @tool
    async def fetch_uniprot_entry(accession: str) -> str:
        """Fetch detailed information for a single UniProt entry by accession ID.
        Returns full sequence, PDB cross-references, gene names, and function
        description for one protein.
        Use ONLY when the user explicitly provides a UniProt accession ID
        (alphanumeric format like Q9HBE4, P00533, O15522).
        Do NOT use for name/gene/keyword searches — use search_uniprot instead."""
        entry = await _fetch(accession)
        if not entry or not entry.get("accession"):
            return f"No UniProt entry found for accession '{accession}'."
        return json.dumps({
            "action": "show_uniprot_detail",
            **entry,
        })

    return fetch_uniprot_entry
