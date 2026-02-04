"""
Pipeline schema definitions for pipeline-canvas backend.
Mirrors frontend pipeline types. No FastAPI or app-specific imports.
"""
from typing import Literal, Dict, Any, List, Optional
from pydantic import BaseModel, Field


# Node types (must match frontend NodeType)
NodeType = Literal[
    "input_node",
    "rfdiffusion_node",
    "proteinmpnn_node",
    "alphafold_node",
    "message_input_node",
    "http_request_node"
]

# Data types for handles (what data flows between nodes)
DataType = Literal["pdb_file", "sequence", "message", "any"]


class NodeHandle(BaseModel):
    """Represents an input or output handle on a node"""
    id: str
    type: Literal["target", "source"]
    position: Literal["left", "right"]
    dataType: Optional[DataType] = None


class NodeSchemaField(BaseModel):
    """Schema definition for a node configuration field"""
    type: Literal["string", "number", "boolean", "select", "textarea", "json"]
    required: bool = False
    default: Any = None
    label: str
    placeholder: Optional[str] = None
    helpText: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    options: Optional[List[Dict[str, str]]] = None


class NodeDefinition(BaseModel):
    """Complete definition of a node type"""
    type: NodeType
    label: str
    description: str
    inputs: List[NodeHandle]
    outputs: List[NodeHandle]
    config_schema: Dict[str, NodeSchemaField]
    default_config: Dict[str, Any]


class PipelineNodeBlueprint(BaseModel):
    """A node in a pipeline blueprint"""
    id: str
    type: NodeType
    label: str
    config: Dict[str, Any] = Field(default_factory=dict)
    inputs: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of input handle IDs to source node IDs"
    )


class PipelineBlueprint(BaseModel):
    """Complete pipeline blueprint structure"""
    rationale: str
    nodes: List[PipelineNodeBlueprint]
    edges: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of edge connections: [{'source': 'node_id', 'target': 'node_id'}]"
    )
    missing_resources: List[str] = Field(
        default_factory=list,
        description="List of missing resources (e.g., ['target_pdb'])"
    )


# Node definitions matching frontend JSON configs
NODE_DEFINITIONS: Dict[NodeType, NodeDefinition] = {
    "input_node": NodeDefinition(
        type="input_node",
        label="Input",
        description="Upload PDB file",
        inputs=[],
        outputs=[
            NodeHandle(id="source", type="source", position="right", dataType="pdb_file")
        ],
        config_schema={
            "filename": NodeSchemaField(type="string", required=False, default="", label="Filename", placeholder="target.pdb")
        },
        default_config={"filename": ""}
    ),
    "rfdiffusion_node": NodeDefinition(
        type="rfdiffusion_node",
        label="RFdiffusion",
        description="De novo backbone design",
        inputs=[NodeHandle(id="target", type="target", position="left", dataType="pdb_file")],
        outputs=[NodeHandle(id="source", type="source", position="right", dataType="pdb_file")],
        config_schema={
            "contigs": NodeSchemaField(type="string", required=False, default="A50-150", label="Contigs", placeholder="A50-150"),
            "num_designs": NodeSchemaField(type="number", required=False, default=1, label="Number of Designs", min=1, max=10),
            "diffusion_steps": NodeSchemaField(type="number", required=False, default=15, label="Diffusion Steps", min=1, max=100),
            "design_mode": NodeSchemaField(type="select", required=False, default="unconditional", label="Design Mode",
                options=[{"value": "unconditional", "label": "Unconditional"}, {"value": "motif_scaffolding", "label": "Motif Scaffolding"}, {"value": "partial_diffusion", "label": "Partial Diffusion"}]),
            "hotspot_res": NodeSchemaField(type="string", required=False, default="", label="Hotspot Residues"),
            "pdb_id": NodeSchemaField(type="string", required=False, default="", label="PDB ID")
        },
        default_config={"contigs": "A50-150", "num_designs": 1, "diffusion_steps": 15, "design_mode": "unconditional", "hotspot_res": "", "pdb_id": ""}
    ),
    "proteinmpnn_node": NodeDefinition(
        type="proteinmpnn_node",
        label="ProteinMPNN",
        description="Sequence design",
        inputs=[NodeHandle(id="target", type="target", position="left", dataType="pdb_file")],
        outputs=[NodeHandle(id="source", type="source", position="right", dataType="sequence")],
        config_schema={
            "num_sequences": NodeSchemaField(type="number", required=False, default=8, label="Number of Sequences", min=1, max=100),
            "temperature": NodeSchemaField(type="number", required=False, default=0.1, label="Temperature", min=0.1, max=1.0, step=0.1)
        },
        default_config={"num_sequences": 8, "temperature": 0.1}
    ),
    "alphafold_node": NodeDefinition(
        type="alphafold_node",
        label="AlphaFold",
        description="Structure prediction",
        inputs=[NodeHandle(id="target", type="target", position="left", dataType="sequence")],
        outputs=[NodeHandle(id="source", type="source", position="right", dataType="pdb_file")],
        config_schema={
            "recycle_count": NodeSchemaField(type="number", required=False, default=3, label="Recycle Count", min=1, max=20),
            "num_relax": NodeSchemaField(type="number", required=False, default=0, label="Number of Relax Steps", min=0, max=10)
        },
        default_config={"recycle_count": 3, "num_relax": 0}
    ),
    "message_input_node": NodeDefinition(
        type="message_input_node",
        label="Message Input",
        description="Input from chat or message",
        inputs=[],
        outputs=[NodeHandle(id="source", type="source", position="right", dataType="any")],
        config_schema={"message": NodeSchemaField(type="string", required=False, default="", label="Message")},
        default_config={"message": ""}
    ),
    "http_request_node": NodeDefinition(
        type="http_request_node",
        label="HTTP Request",
        description="Generic HTTP API call",
        inputs=[NodeHandle(id="target", type="target", position="left", dataType="any")],
        outputs=[NodeHandle(id="source", type="source", position="right", dataType="any")],
        config_schema={
            "url": NodeSchemaField(type="string", required=False, default="", label="URL"),
            "method": NodeSchemaField(type="string", required=False, default="GET", label="Method")
        },
        default_config={"url": "", "method": "GET"}
    ),
}


def can_connect(source_type: NodeType, target_type: NodeType) -> bool:
    """Check if two nodes can be connected based on their data types."""
    if source_type not in NODE_DEFINITIONS or target_type not in NODE_DEFINITIONS:
        return False
    source_def = NODE_DEFINITIONS[source_type]
    target_def = NODE_DEFINITIONS[target_type]
    source_outputs = {h.dataType for h in source_def.outputs if h.dataType}
    target_inputs = {h.dataType for h in target_def.inputs if h.dataType}
    if "any" in source_outputs or "any" in target_inputs:
        return True
    return bool(source_outputs & target_inputs)


def get_default_config(node_type: NodeType) -> Dict[str, Any]:
    """Get default configuration for a node type"""
    if node_type not in NODE_DEFINITIONS:
        return {}
    return NODE_DEFINITIONS[node_type].default_config.copy()


def validate_blueprint(blueprint: PipelineBlueprint) -> List[str]:
    """Validate a pipeline blueprint and return list of errors."""
    errors: List[str] = []
    node_ids = [node.id for node in blueprint.nodes]
    if len(node_ids) != len(set(node_ids)):
        errors.append("Duplicate node IDs found")
    all_node_ids = set(node_ids)
    for edge in blueprint.edges:
        if edge.get("source") not in all_node_ids:
            errors.append(f"Edge references non-existent source node: {edge.get('source')}")
        if edge.get("target") not in all_node_ids:
            errors.append(f"Edge references non-existent target node: {edge.get('target')}")
    for node in blueprint.nodes:
        if node.type not in NODE_DEFINITIONS:
            errors.append(f"Unknown node type: {node.type}")
    for edge in blueprint.edges:
        source_node = next((n for n in blueprint.nodes if n.id == edge.get("source")), None)
        target_node = next((n for n in blueprint.nodes if n.id == edge.get("target")), None)
        if source_node and target_node and not can_connect(source_node.type, target_node.type):
            errors.append(f"Cannot connect {source_node.type} to {target_node.type}: incompatible data types")
    return errors
