"""LangChain tools for agents."""

from .smiles import get_smiles_tool
from .actions import get_action_tools
from .actions import get_uniprot_tool as _get_uniprot_tool_legacy  # keep for backward compat

# Individual tool modules
from .alphafold import get_alphafold_tool
from .openfold import get_openfold_tool
from .rfdiffusion import get_rfdiffusion_tool
from .proteinmpnn import get_proteinmpnn_tool
from .diffdock import get_diffdock_tool
from .validation import get_validation_tool
from .uniprot import get_uniprot_tool
from .mvs_builder import get_mvs_builder_tool


# ---- Agent → Tool mapping for supervisor pattern ----

AGENT_TOOL_MAP = {
    "bio_chat": [
        get_validation_tool,
        get_uniprot_tool,
        get_mvs_builder_tool,
    ],
    "code_builder": [
        get_smiles_tool,
        get_mvs_builder_tool,
    ],
    "pipeline": [],
}


def get_tools_for_agent(agent_id: str) -> list:
    """Return instantiated LangChain tools for the given agent."""
    factories = AGENT_TOOL_MAP.get(agent_id, [])
    return [f() for f in factories]


# ---- Legacy single-agent helper (backward compat) ----

def get_all_react_tools():
    """All tools for the legacy single ReAct agent."""
    tools = [get_smiles_tool(), get_uniprot_tool()]
    tools.extend(get_action_tools())
    return tools


__all__ = [
    "get_smiles_tool",
    "get_action_tools",
    "get_uniprot_tool",
    "get_all_react_tools",
    "get_tools_for_agent",
    "get_alphafold_tool",
    "get_openfold_tool",
    "get_rfdiffusion_tool",
    "get_proteinmpnn_tool",
    "get_diffdock_tool",
    "get_validation_tool",
    "get_mvs_builder_tool",
    "AGENT_TOOL_MAP",
]
