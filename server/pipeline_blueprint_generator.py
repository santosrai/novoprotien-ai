"""
Pipeline blueprint generator utilities.
Provides helper functions for creating and validating pipeline blueprints.
"""
from typing import Dict, Any, List, Optional
import uuid
from .pipeline_schema import (
    PipelineBlueprint,
    PipelineNodeBlueprint,
    NodeType,
    NODE_DEFINITIONS,
    can_connect,
    get_default_config,
    validate_blueprint
)


def generate_node_id(node_type: NodeType, index: int = 1) -> str:
    """
    Generate a unique node ID based on node type.
    
    Args:
        node_type: The type of node
        index: Optional index for multiple nodes of same type
    
    Returns:
        Unique node ID string
    """
    prefix_map = {
        "input_node": "input",
        "rfdiffusion_node": "rfd",
        "proteinmpnn_node": "pm",
        "alphafold_node": "af",
        "message_input_node": "msg",
        "http_request_node": "http"
    }
    prefix = prefix_map.get(node_type, "node")
    return f"{prefix}_{index}_{uuid.uuid4().hex[:6]}"


def create_node(
    node_type: NodeType,
    label: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    node_id: Optional[str] = None
) -> PipelineNodeBlueprint:
    """
    Create a pipeline node with default configuration.
    
    Args:
        node_type: Type of node to create
        label: Optional custom label (defaults to node definition label)
        config: Optional config overrides (merged with defaults)
        node_id: Optional custom node ID (auto-generated if not provided)
    
    Returns:
        PipelineNodeBlueprint instance
    """
    if node_type not in NODE_DEFINITIONS:
        raise ValueError(f"Unknown node type: {node_type}")
    
    node_def = NODE_DEFINITIONS[node_type]
    default_config = get_default_config(node_type)
    
    # Merge provided config with defaults
    final_config = {**default_config}
    if config:
        final_config.update(config)
    
    return PipelineNodeBlueprint(
        id=node_id or generate_node_id(node_type),
        type=node_type,
        label=label or node_def.label,
        config=final_config,
        inputs={}
    )


def create_edge(source_node_id: str, target_node_id: str) -> Dict[str, str]:
    """
    Create an edge connection between two nodes.
    
    Args:
        source_node_id: ID of source node
        target_node_id: ID of target node
    
    Returns:
        Edge dictionary
    """
    return {"source": source_node_id, "target": target_node_id}


def create_simple_pipeline(
    workflow_type: str,
    context: Dict[str, Any]
) -> PipelineBlueprint:
    """
    Create a simple pipeline based on workflow type.
    This is a helper function - the AI agent will generate more complex pipelines.
    
    Args:
        workflow_type: Type of workflow ("design", "fold", "redesign", "full")
        context: Context from get_pipeline_context()
    
    Returns:
        PipelineBlueprint instance
    """
    nodes: List[PipelineNodeBlueprint] = []
    edges: List[Dict[str, str]] = []
    missing_resources: List[str] = []
    
    # Check for available files
    uploaded_files = context.get("uploaded_files", [])
    canvas_structure = context.get("canvas_structure")
    
    has_file = len(uploaded_files) > 0 or canvas_structure is not None
    
    if workflow_type == "design" and has_file:
        # Design workflow: input → RFdiffusion
        input_node = create_node(
            "input_node",
            config={
                "filename": uploaded_files[0].get("filename", "") if uploaded_files else "",
                "file_id": uploaded_files[0].get("file_id", "") if uploaded_files else ""
            }
        )
        nodes.append(input_node)
        
        rfd_node = create_node(
            "rfdiffusion_node",
            config={
                "contigs": uploaded_files[0].get("suggested_contigs", "A50-150") if uploaded_files else "A50-150"
            }
        )
        nodes.append(rfd_node)
        edges.append(create_edge(input_node.id, rfd_node.id))
        
    elif workflow_type == "redesign" and has_file:
        # Redesign workflow: input → ProteinMPNN
        input_node = create_node(
            "input_node",
            config={
                "filename": uploaded_files[0].get("filename", "") if uploaded_files else "",
                "file_id": uploaded_files[0].get("file_id", "") if uploaded_files else ""
            }
        )
        nodes.append(input_node)
        
        pm_node = create_node("proteinmpnn_node")
        nodes.append(pm_node)
        edges.append(create_edge(input_node.id, pm_node.id))
        
    elif workflow_type == "full" and has_file:
        # Full workflow: input → RFdiffusion → ProteinMPNN → AlphaFold
        input_node = create_node(
            "input_node",
            config={
                "filename": uploaded_files[0].get("filename", "") if uploaded_files else "",
                "file_id": uploaded_files[0].get("file_id", "") if uploaded_files else ""
            }
        )
        nodes.append(input_node)
        
        rfd_node = create_node(
            "rfdiffusion_node",
            config={
                "contigs": uploaded_files[0].get("suggested_contigs", "A50-150") if uploaded_files else "A50-150"
            }
        )
        nodes.append(rfd_node)
        edges.append(create_edge(input_node.id, rfd_node.id))
        
        pm_node = create_node("proteinmpnn_node")
        nodes.append(pm_node)
        edges.append(create_edge(rfd_node.id, pm_node.id))
        
        af_node = create_node("alphafold_node")
        nodes.append(af_node)
        edges.append(create_edge(pm_node.id, af_node.id))
        
    else:
        # Missing resources
        missing_resources.append("target_pdb")
    
    rationale = f"Created {workflow_type} workflow pipeline"
    if missing_resources:
        rationale += f" (missing: {', '.join(missing_resources)})"
    
    return PipelineBlueprint(
        rationale=rationale,
        nodes=nodes,
        edges=edges,
        missing_resources=missing_resources
    )


def validate_and_fix_blueprint(blueprint: PipelineBlueprint) -> tuple[PipelineBlueprint, List[str]]:
    """
    Validate a blueprint and attempt to fix common issues.
    
    Args:
        blueprint: The blueprint to validate
    
    Returns:
        Tuple of (fixed_blueprint, list_of_warnings)
    """
    errors = validate_blueprint(blueprint)
    warnings: List[str] = []
    
    # If there are errors, try to fix them
    if errors:
        # Try to fix duplicate IDs
        seen_ids = set()
        for node in blueprint.nodes:
            if node.id in seen_ids:
                # Generate new ID
                node.id = generate_node_id(node.type)
            seen_ids.add(node.id)
        
        # Remove invalid edges
        valid_node_ids = {node.id for node in blueprint.nodes}
        blueprint.edges = [
            edge for edge in blueprint.edges
            if edge.get("source") in valid_node_ids and edge.get("target") in valid_node_ids
        ]
        
        # Re-validate
        errors = validate_blueprint(blueprint)
    
    return blueprint, warnings

