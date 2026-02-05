"""
Context gathering for pipeline agent.
Collects information about available files, canvas state, and chat history.
"""
from typing import Dict, Any, List, Optional
from ..storage.pdb_storage import get_uploaded_pdb, list_uploaded_pdbs


async def get_pipeline_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gather all context the pipeline agent needs to create pipelines or answer questions about pipelines.
    
    Args:
        state: Request state containing uploadedFileId, canvasStructure, history, pipeline_id, etc.
    
    Returns:
        Context dictionary with available resources and information, including pipeline data if pipeline_id is provided
    """
    context: Dict[str, Any] = {
        "uploaded_files": [],
        "canvas_structure": None,
        "recent_chat_history": [],
        "pipeline": None,  # Will be populated if pipeline_id is provided
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
    
    # Check for pipeline_id - if provided, fetch pipeline data
    pipeline_id = state.get("pipeline_id")
    if pipeline_id:
        try:
            # If pipeline_data is provided in state, use it to create full summary
            pipeline_data = state.get("pipeline_data")
            if pipeline_data:
                summary = await get_pipeline_summary(pipeline_id, pipeline_data)
                context["pipeline"] = summary
                
                # Extract output files from node result_metadata
                output_files = []
                nodes = pipeline_data.get("nodes", [])
                for node in nodes:
                    result_metadata = node.get("result_metadata", {})
                    if result_metadata.get("output_file"):
                        output_files.append({
                            "node_id": node.get("id"),
                            "node_label": node.get("label"),
                            "node_type": node.get("type"),
                            "file": result_metadata["output_file"],
                        })
                    # Also check for sequence outputs
                    if result_metadata.get("sequence"):
                        output_files.append({
                            "node_id": node.get("id"),
                            "node_label": node.get("label"),
                            "node_type": node.get("type"),
                            "type": "sequence",
                            "sequence": result_metadata["sequence"],
                        })
                
                if output_files:
                    context["pipeline"]["output_files"] = output_files
            else:
                # If no pipeline_data, create a basic structure indicating pipeline is attached
                # This ensures the agent knows a pipeline is referenced even if full data isn't available
                context["pipeline"] = {
                    "id": pipeline_id,
                    "name": "Attached Pipeline",
                    "status": "unknown",
                    "node_count": 0,
                    "note": f"Pipeline ID {pipeline_id} is attached to this message. Full pipeline details are not available (user may not be authenticated or pipeline may not exist in database). The user is asking about this pipeline.",
                }
        except Exception as e:
            # If pipeline fetching fails, log but continue without pipeline context
            import logging
            logging.warning(f"Failed to fetch pipeline context for {pipeline_id}: {e}")
            context["pipeline"] = {
                "id": pipeline_id,
                "name": "Attached Pipeline",
                "error": "Failed to load pipeline data",
                "note": f"Pipeline ID {pipeline_id} is attached but could not be loaded. The user is asking about this pipeline.",
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


async def get_pipeline_summary(pipeline_id: str, pipeline_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a summary of the current pipeline for AI context.
    
    Args:
        pipeline_id: ID of the pipeline
        pipeline_data: Full pipeline data from frontend
    
    Returns:
        Summary dictionary with pipeline information
    """
    nodes = pipeline_data.get("nodes", [])
    edges = pipeline_data.get("edges", [])
    
    # Group nodes by type
    nodes_by_type = {}
    for node in nodes:
        node_type = node.get("type", "unknown")
        if node_type not in nodes_by_type:
            nodes_by_type[node_type] = []
        nodes_by_type[node_type].append({
            "id": node.get("id"),
            "label": node.get("label"),
            "status": node.get("status"),
            "config": node.get("config", {}),
        })
    
    # Build execution flow description
    execution_flow = []
    input_nodes = [n for n in nodes if n.get("type") == "input_node"]
    
    for input_node in input_nodes:
        flow = [input_node.get("label", input_node.get("id"))]
        # Follow edges to find downstream nodes
        current_node_id = input_node.get("id")
        visited = {current_node_id}
        
        while True:
            downstream_edges = [e for e in edges if e.get("source") == current_node_id]
            if not downstream_edges:
                break
            next_edge = downstream_edges[0]
            next_node_id = next_edge.get("target")
            if next_node_id in visited:
                break
            visited.add(next_node_id)
            next_node = next((n for n in nodes if n.get("id") == next_node_id), None)
            if not next_node:
                break
            flow.append(next_node.get("label", next_node.get("id")))
            current_node_id = next_node_id
        
        execution_flow.append(" → ".join(flow))
    
    # If no input nodes, try to find any starting nodes (nodes with no incoming edges)
    if not execution_flow:
        nodes_with_incoming = {e.get("target") for e in edges}
        starting_nodes = [n for n in nodes if n.get("id") not in nodes_with_incoming]
        for start_node in starting_nodes:
            execution_flow.append(start_node.get("label", start_node.get("id")))
    
    summary = {
        "pipeline_id": pipeline_id,
        "name": pipeline_data.get("name", "Unnamed Pipeline"),
        "status": pipeline_data.get("status", "draft"),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes_by_type": nodes_by_type,
        "execution_flow": execution_flow if execution_flow else ["No execution flow detected"],
        "node_details": [
            {
                "id": node.get("id"),
                "type": node.get("type"),
                "label": node.get("label"),
                "status": node.get("status"),
                "has_config": bool(node.get("config")),
            }
            for node in nodes
        ],
    }
    
    return summary

