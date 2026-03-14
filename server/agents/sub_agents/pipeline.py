"""Pipeline sub-agent: workflow composition and blueprint generation."""

from __future__ import annotations

from typing import Any, Optional

try:
    from ..langchain_agent.graph import build_agent_graph
    from ..llm.model import get_chat_model
    from ..prompts.pipeline import PIPELINE_AGENT_SYSTEM_PROMPT
except ImportError:
    from agents.langchain_agent.graph import build_agent_graph
    from agents.llm.model import get_chat_model
    from agents.prompts.pipeline import PIPELINE_AGENT_SYSTEM_PROMPT


def build_pipeline_agent(
    model_id: str,
    api_key: Optional[str] = None,
    temperature: float = 0.5,
    max_tokens: int = 2000,
) -> Any:
    """Build a ReAct agent for pipeline blueprint generation.

    No tools — the Pipeline agent generates JSON blueprints in its text response.
    """
    llm = get_chat_model(model_id, api_key, temperature=temperature, max_tokens=max_tokens)
    tools = []  # Pipeline agent generates blueprints as text, no tool calls
    return build_agent_graph(llm, tools, system_prompt=PIPELINE_AGENT_SYSTEM_PROMPT)
