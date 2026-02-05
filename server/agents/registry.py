"""Agent registry and definitions."""

import os
from .prompts.code_builder import CODE_AGENT_SYSTEM_PROMPT
from .prompts.mvs_builder import MVS_AGENT_SYSTEM_PROMPT_BASE
from .prompts.bio_chat import BIO_CHAT_SYSTEM_PROMPT
from .prompts.alphafold import ALPHAFOLD_AGENT_SYSTEM_PROMPT
from .prompts.openfold2 import OPENFOLD2_AGENT_SYSTEM_PROMPT
from .prompts.rfdiffusion import RFDIFFUSION_AGENT_SYSTEM_PROMPT
from .prompts.proteinmpnn import PROTEINMPNN_AGENT_SYSTEM_PROMPT
from .prompts.pipeline import PIPELINE_AGENT_SYSTEM_PROMPT


agents = {
    "code-builder": {
        "id": "code-builder",
        "name": "Mol* Code Builder Agent",
        "description": "Generates runnable Molstar builder JavaScript for simple protein visualization and basic representation changes.",
        "system": CODE_AGENT_SYSTEM_PROMPT,
        "modelEnv": "CLAUDE_CODE_MODEL",
        "defaultModel": os.getenv("CLAUDE_CODE_MODEL", "claude-3-5-sonnet-20241022"),
        "kind": "code",
        "category": "code",
    },
    "mvs-builder": {
        "id": "mvs-builder",
        "name": "MolViewSpec Code Builder",
        "description": "Generates MolViewSpec fluent API code for complex molecular scenes with custom labels, annotations, multiple components, and declarative specifications. Use for: adding text labels to proteins, labeling ligands, custom annotations, complex molecular visualizations, multi-component scenes, labeling chains, annotating binding sites, adding custom text to molecular structures, coloring with labels, focus with labels, surface with annotations.",
        "system": MVS_AGENT_SYSTEM_PROMPT_BASE,
        "modelEnv": "CLAUDE_CODE_MODEL",
        "defaultModel": os.getenv("CLAUDE_CODE_MODEL", "claude-3-5-sonnet-20241022"),
        "kind": "code",
        "category": "plan",
    },
    "bio-chat": {
        "id": "bio-chat",
        "name": "Protein Info Agent",
        "description": "Answers questions about proteins, PDB data, and structural biology.",
        "system": BIO_CHAT_SYSTEM_PROMPT,
        "modelEnv": "CLAUDE_CHAT_MODEL",
        "defaultModel": os.getenv("CLAUDE_CHAT_MODEL", "claude-3-5-sonnet-20241022"),
        "kind": "text",
        "category": "ask",
    },
    "uniprot-search": {
        "id": "uniprot-search",
        "name": "UniProt Search",
        "description": "Searches UniProtKB and returns top entries as table/json/csv.",
        "system": "",
        "modelEnv": "",
        "defaultModel": "",
        "kind": "text",
        "category": "ask",
    },
    "alphafold-agent": {
        "id": "alphafold-agent",
        "name": "AlphaFold2 Structure Prediction",
        "description": "Performs protein structure prediction using AlphaFold2 via NVIDIA NIMS API. Handles protein folding, docking, sequence extraction from PDB IDs, chain-specific folding, residue range selection, parameter configuration for MSA algorithms, databases, and folding options. Provides folded structures for MolStar visualization with progress tracking.",
        "system": ALPHAFOLD_AGENT_SYSTEM_PROMPT,
        "modelEnv": "CLAUDE_CHAT_MODEL",
        "defaultModel": os.getenv("CLAUDE_CHAT_MODEL", "claude-3-5-sonnet-20241022"),
        "kind": "alphafold",
        "category": "fold",
    },
    "openfold2-agent": {
        "id": "openfold2-agent",
        "name": "OpenFold2 Structure Prediction",
        "description": "Predicts protein 3D structures using OpenFold2 via NVIDIA NIM. Supports sequence-only or sequence with optional MSA (a3m) and template (hhr) uploads. Max 1000 residues. Use for structure prediction when you have pre-computed MSA or want an alternative to AlphaFold2.",
        "system": OPENFOLD2_AGENT_SYSTEM_PROMPT,
        "modelEnv": "CLAUDE_CHAT_MODEL",
        "defaultModel": os.getenv("CLAUDE_CHAT_MODEL", "claude-3-5-sonnet-20241022"),
        "kind": "openfold2",
        "category": "fold",
    },
    "rfdiffusion-agent": {
        "id": "rfdiffusion-agent",
        "name": "RFdiffusion Protein Design",
        "description": "Performs de novo protein design using RFdiffusion via NVIDIA NIMS API. Handles unconditional protein generation, motif scaffolding, hotspot-based design, and template-guided protein creation. Configures contigs, diffusion steps, and design complexity for creating novel protein structures.",
        "system": RFDIFFUSION_AGENT_SYSTEM_PROMPT,
        "modelEnv": "CLAUDE_CHAT_MODEL",
        "defaultModel": os.getenv("CLAUDE_CHAT_MODEL", "claude-3-5-sonnet-20241022"),
        "kind": "rfdiffusion",
        "category": "design",
    },
    "proteinmpnn-agent": {
        "id": "proteinmpnn-agent",
        "name": "ProteinMPNN Sequence Design",
        "description": "Designs amino-acid sequences for an existing protein backbone using NVIDIA's ProteinMPNN inverse folding API. Supports RFdiffusion outputs, uploaded structures, chain filtering, residue constraints, and multi-sequence generation with tunable temperature and randomness.",
        "system": PROTEINMPNN_AGENT_SYSTEM_PROMPT,
        "modelEnv": "CLAUDE_CHAT_MODEL",
        "defaultModel": os.getenv("CLAUDE_CHAT_MODEL", "claude-3-5-sonnet-20241022"),
        "kind": "proteinmpnn",
        "category": "design",
    },
    "pipeline-agent": {
        "id": "pipeline-agent",
        "name": "Pipeline Architect",
        "description": "Creates protein design workflows by generating pipeline blueprints that connect multiple tools (RFdiffusion, ProteinMPNN, AlphaFold). Analyzes user requests and available resources to design appropriate workflows.",
        "system": PIPELINE_AGENT_SYSTEM_PROMPT,
        "modelEnv": "CLAUDE_CHAT_MODEL",
        "defaultModel": os.getenv("CLAUDE_CHAT_MODEL", "claude-3-5-sonnet-20241022"),
        "kind": "pipeline",
        "category": "workflow",
    },
}


def list_agents():
    return [
        {
            "id": a["id"],
            "name": a["name"],
            "description": a["description"],
            "kind": a["kind"],
            "category": a.get("category", "other"),
        }
        for a in agents.values()
    ]

