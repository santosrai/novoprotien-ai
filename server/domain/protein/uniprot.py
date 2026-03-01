from typing import Any, Dict, List
import httpx

UNIPROT_SEARCH_BASE = "https://rest.uniprot.org/uniprotkb/search"
UNIPROT_ENTRY_BASE = "https://rest.uniprot.org/uniprotkb"


async def search_uniprot(query: str, size: int = 5) -> List[Dict[str, Any]]:
    """Search UniProt for proteins. Returns accession, name, organism, length,
    sequence (truncated), PDB cross-references, and review status."""
    params = {
        "query": query,
        "format": "json",
        "size": str(size),
        "fields": "accession,id,protein_name,organism_name,length,reviewed,sequence,xref_pdb",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(UNIPROT_SEARCH_BASE, params=params)
        resp.raise_for_status()
        data = resp.json() or {}

    results: List[Dict[str, Any]] = []
    for item in (data.get("results") or [])[:size]:
        protein_desc = (item.get("proteinDescription") or {}).get("recommendedName") or {}
        full_name = (protein_desc.get("fullName") or {}).get("value") if protein_desc else None

        # Full sequence
        sequence_value = (item.get("sequence") or {}).get("value", "")

        # PDB cross-references
        xrefs = item.get("uniProtKBCrossReferences") or []
        pdb_ids = [x["id"] for x in xrefs if x.get("database") == "PDB"]

        results.append(
            {
                "accession": item.get("primaryAccession"),
                "id": item.get("uniProtkbId"),
                "protein": full_name,
                "organism": (item.get("organism") or {}).get("scientificName"),
                "length": (item.get("sequence") or {}).get("length"),
                "reviewed": item.get("entryType") == "Reviewed",
                "sequence": sequence_value,
                "pdb_ids": pdb_ids,
            }
        )
    return results


async def fetch_uniprot_entry(accession: str) -> Dict[str, Any]:
    """Fetch detailed info for a single UniProt accession."""
    url = f"{UNIPROT_ENTRY_BASE}/{accession.strip()}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params={"format": "json"})
        resp.raise_for_status()
        data = resp.json() or {}

    # Protein name
    protein_desc = (data.get("proteinDescription") or {}).get("recommendedName") or {}
    full_name = (protein_desc.get("fullName") or {}).get("value") if protein_desc else None

    # Sequence
    sequence_value = (data.get("sequence") or {}).get("value", "")
    seq_length = (data.get("sequence") or {}).get("length")

    # PDB cross-references
    xrefs = data.get("uniProtKBCrossReferences") or []
    pdb_ids = [x["id"] for x in xrefs if x.get("database") == "PDB"]

    # Gene names
    gene_names = []
    for gene in data.get("genes") or []:
        name = (gene.get("geneName") or {}).get("value")
        if name:
            gene_names.append(name)

    # Function description
    function_description = None
    for comment in data.get("comments") or []:
        if comment.get("commentType") == "FUNCTION":
            texts = comment.get("texts") or []
            if texts:
                function_description = texts[0].get("value")
            break

    # Organism
    organism = (data.get("organism") or {}).get("scientificName")

    return {
        "accession": data.get("primaryAccession"),
        "id": data.get("uniProtkbId"),
        "protein": full_name,
        "organism": organism,
        "length": seq_length,
        "sequence": sequence_value,
        "pdb_ids": pdb_ids,
        "gene_names": gene_names,
        "function_description": function_description,
        "reviewed": data.get("entryType") == "Reviewed",
    }
