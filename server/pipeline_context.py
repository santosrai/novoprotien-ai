"""
Context gathering for pipeline agent.
Collects information about available files, canvas state, and chat history.
"""
from typing import Dict, Any, List, Optional
from .pdb_storage import get_uploaded_pdb, list_uploaded_pdbs


async def get_pipeline_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gather all context the pipeline agent needs to create pipelines.
    
    Args:
        state: Request state containing uploadedFileId, canvasStructure, history, etc.
    
    Returns:
        Context dictionary with available resources and information
    """
    context: Dict[str, Any] = {
        "uploaded_files": [],
        "canvas_structure": None,
        "recent_chat_history": [],
        "available_node_types": [
            "input_node",
            "rfdiffusion_node",
            "proteinmpnn_node",
            "alphafold_node"
        ],
        "node_capabilities": {
            "input_node": {
                "outputs": ["pdb_file"],
                "description": "Upload PDB file"
            },
            "rfdiffusion_node": {
                "inputs": ["pdb_file"],
                "outputs": ["pdb_file"],
                "description": "De novo backbone design"
            },
            "proteinmpnn_node": {
                "inputs": ["pdb_file"],
                "outputs": ["sequence"],
                "description": "Sequence design"
            },
            "alphafold_node": {
                "inputs": ["sequence"],
                "outputs": ["pdb_file"],
                "description": "Structure prediction"
            }
        }
    }
    
    # Check for uploaded file ID
    uploaded_file_id = state.get("uploadedFileId")
    if uploaded_file_id:
        file_metadata = get_uploaded_pdb(uploaded_file_id)
        if file_metadata:
            context["uploaded_files"].append({
                "file_id": file_metadata.get("file_id"),
                "filename": file_metadata.get("filename"),
                "type": "pdb_file",
                "atoms": file_metadata.get("atoms"),
                "chains": file_metadata.get("chains", []),
                "chain_residue_counts": file_metadata.get("chain_residue_counts", {}),
                "total_residues": file_metadata.get("total_residues"),
                "suggested_contigs": file_metadata.get("suggested_contigs"),
                "file_url": f"/api/upload/pdb/{uploaded_file_id}"
            })
    
    # Check for canvas structure (3D viewer state)
    canvas_structure = state.get("currentStructureOrigin")
    if canvas_structure:
        # Extract PDB ID or file info from canvas
        if isinstance(canvas_structure, str):
            # Could be a PDB ID like "1ABC" or a file URL
            if len(canvas_structure) == 4 and canvas_structure.isalnum():
                # Likely a PDB ID
                context["canvas_structure"] = {
                    "pdb_id": canvas_structure,
                    "type": "pdb_id"
                }
            elif canvas_structure.startswith("/api/upload/pdb/"):
                # Uploaded file URL
                file_id = canvas_structure.split("/")[-1]
                file_metadata = get_uploaded_pdb(file_id)
                if file_metadata:
                    context["canvas_structure"] = {
                        "file_id": file_id,
                        "filename": file_metadata.get("filename"),
                        "type": "uploaded_file",
                        "file_url": canvas_structure
                    }
        elif isinstance(canvas_structure, dict):
            # Structured canvas data
            context["canvas_structure"] = {
                "pdb_id": canvas_structure.get("pdbId"),
                "file_id": canvas_structure.get("fileId"),
                "chains": canvas_structure.get("chains", []),
                "type": canvas_structure.get("type", "unknown")
            }
    
    # Check chat history for file references
    history = state.get("history", [])
    if history:
        # Extract last few messages for context
        recent_history = history[-10:] if len(history) > 10 else history
        context["recent_chat_history"] = recent_history
        
        # Look for file references in history
        for message in recent_history:
            content = message.get("content", "")
            if isinstance(content, str):
                # Check for PDB IDs (4-character codes)
                import re
                pdb_matches = re.findall(r'\b([A-Z0-9]{4})\b', content.upper())
                if pdb_matches:
                    for pdb_id in pdb_matches:
                        if pdb_id not in [f.get("pdb_id") for f in context.get("referenced_pdbs", [])]:
                            if "referenced_pdbs" not in context:
                                context["referenced_pdbs"] = []
                            context["referenced_pdbs"].append({
                                "pdb_id": pdb_id,
                                "type": "pdb_id",
                                "source": "chat_history"
                            })
    
    # Also check for any recently uploaded files (last 5)
    recent_files = list_uploaded_pdbs()[:5]
    if recent_files:
        context["recent_files"] = [
            {
                "file_id": f.get("file_id"),
                "filename": f.get("filename"),
                "atoms": f.get("atoms"),
                "chains": f.get("chains", []),
                "total_residues": f.get("total_residues")
            }
            for f in recent_files
        ]
    
    return context

