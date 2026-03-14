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
        Returns a list of up to 5 matching entries (accession, name, organism,
        length, sequence preview, PDB cross-references) displayed as a results card.
        Use this tool whenever the user wants to find, discover, search, or list
        proteins — even if you already know the accession. Always prefer this
        tool over fetch_uniprot_entry for name/gene/keyword queries so the user
        can see all matching results."""
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
