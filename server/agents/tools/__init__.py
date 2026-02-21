"""LangChain tools for agents."""

from .smiles import get_smiles_tool
from .actions import get_action_tools, get_uniprot_tool


def get_all_react_tools():
    """All tools for the ReAct agent: SMILES, UniProt, and open-dialog actions."""
    tools = [get_smiles_tool(), get_uniprot_tool()]
    tools.extend(get_action_tools())
    return tools


__all__ = ["get_smiles_tool", "get_action_tools", "get_uniprot_tool", "get_all_react_tools"]
