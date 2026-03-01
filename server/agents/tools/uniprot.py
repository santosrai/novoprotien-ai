"""LangChain tool: search UniProt for protein entries."""

from __future__ import annotations

import json

try:
    from langchain_core.tools import tool
except ImportError:
    tool = None


def get_uniprot_tool():
    """Return a LangChain tool that searches UniProt (async)."""
    if tool is None:
        raise RuntimeError("langchain_core.tools is required")

    try:
        from ...domain.protein.uniprot import search_uniprot as _search_uniprot
    except ImportError:
        from domain.protein.uniprot import search_uniprot as _search_uniprot

    @tool
    async def search_uniprot(query: str, size: int = 5) -> str:
        """Search UniProt for proteins by name, gene, organism, or keyword.
        Returns structured JSON with accession, name, organism, length,
        sequence preview, and PDB cross-references.
        Use when the user asks to search UniProt, find a protein in UniProt,
        or look up a protein by name/gene."""
        items = await _search_uniprot(query, size=size)
        if not items:
            return "No UniProt entries found for that query."
        # Return JSON so it flows as structured data to the frontend
        return json.dumps({
            "action": "show_uniprot_results",
            "query": query,
            "results": items,
            "count": len(items),
        })

    return search_uniprot
