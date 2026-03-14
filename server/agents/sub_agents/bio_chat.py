"""BioChat sub-agent: protein Q&A, info retrieval, and computational tool triggers."""

from __future__ import annotations

from typing import Any, Optional

try:
    from ..langchain_agent.graph import build_agent_graph
    from ..llm.model import get_chat_model
    from ..tools import get_tools_for_agent
    from ..prompts.bio_chat import BIO_CHAT_SYSTEM_PROMPT
except ImportError:
    from agents.langchain_agent.graph import build_agent_graph
    from agents.llm.model import get_chat_model
    from agents.tools import get_tools_for_agent
    from agents.prompts.bio_chat import BIO_CHAT_SYSTEM_PROMPT


def build_bio_chat_agent(
    model_id: str,
    api_key: Optional[str] = None,
    temperature: float = 0.5,
    max_tokens: int = 1000,
) -> Any:
    """Build a ReAct agent for BioChat with all computational tools.

    Tools: AlphaFold, OpenFold, RFdiffusion, ProteinMPNN, DiffDock,
           Validation, UniProt, MVS Builder.
    """
    llm = get_chat_model(model_id, api_key, temperature=temperature, max_tokens=max_tokens)
    tools = get_tools_for_agent("bio_chat")
    return build_agent_graph(llm, tools, system_prompt=BIO_CHAT_SYSTEM_PROMPT)
