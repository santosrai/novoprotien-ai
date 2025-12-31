from typing import Any, Dict, List
import httpx

UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb/search"


async def search_uniprot(query: str, size: int = 3) -> List[Dict[str, Any]]:
    params = {
        "query": query,
        "format": "json",
        "size": str(size),
        "fields": "accession,id,protein_name,organism_name,length,reviewed",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(UNIPROT_BASE, params=params)
        resp.raise_for_status()
        data = resp.json() or {}

    results: List[Dict[str, Any]] = []
    for item in (data.get("results") or [])[:size]:
        protein_desc = (item.get("proteinDescription") or {}).get("recommendedName") or {}
        full_name = (protein_desc.get("fullName") or {}).get("value") if protein_desc else None
        results.append(
            {
                "accession": item.get("primaryAccession"),
                "id": item.get("uniProtkbId"),
                "protein": full_name,
                "organism": (item.get("organism") or {}).get("scientificName"),
                "length": (item.get("sequence") or {}).get("length"),
                "reviewed": item.get("entryType") == "Reviewed",
            }
        )
    return results

