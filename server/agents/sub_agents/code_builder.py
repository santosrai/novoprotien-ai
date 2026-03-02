"""Code Builder sub-agent: MolStar / MolViewSpec visualization code generation."""

from __future__ import annotations

from typing import Any, Optional

try:
    from ..langchain_agent.graph import build_agent_graph
    from ..llm.model import get_chat_model
    from ..tools import get_tools_for_agent
    from ..prompts.code_builder import CODE_AGENT_SYSTEM_PROMPT
    from ..prompts.mvs_builder import MVS_AGENT_SYSTEM_PROMPT_BASE
except ImportError:
    from agents.langchain_agent.graph import build_agent_graph
    from agents.llm.model import get_chat_model
    from agents.tools import get_tools_for_agent
    from agents.prompts.code_builder import CODE_AGENT_SYSTEM_PROMPT
    from agents.prompts.mvs_builder import MVS_AGENT_SYSTEM_PROMPT_BASE


# Fix 5: Keywords that signal the user needs the full MVS API docs.
# Most simple viz requests ("show 1ZNI", "highlight residue 50") only need
# the builder API (~1050 tokens). Including MVS (~2325 tokens) only when needed.
_MVS_KEYWORDS = frozenset({
    "opacity", "transparent", "transparency", "assembly", "symmetry",
    "volume", "density", "primitive", "arrow", "measurement", "distance",
    "compare", "overlay", "two structures", "annotation", "mvs",
    "molviewspec", "canvas", "background", "camera", "isosurface",
})


async def _build_code_builder_prompt(user_query: str = "") -> str:
    """Merge Mol* + MVS system prompts, then enhance with RAG examples.

    Fix 5: Only include the heavy MVS prompt (~2325 tokens) when the user
    query contains MVS-related keywords.  Otherwise just the builder API.
    """
    query_lower = (user_query or "").lower()
    needs_mvs = any(kw in query_lower for kw in _MVS_KEYWORDS)

    if needs_mvs:
        merged = (
            CODE_AGENT_SYSTEM_PROMPT
            + "\n\n--- MolViewSpec (MVS) Fluent API ---\n\n"
            + MVS_AGENT_SYSTEM_PROMPT_BASE
        )
    else:
        merged = CODE_AGENT_SYSTEM_PROMPT  # builder API only

    if not user_query:
        return merged

    # Try RAG enhancement
    try:
        try:
            from ...memory.rag.mvs_rag import enhance_mvs_prompt_with_rag
        except ImportError:
            from memory.rag.mvs_rag import enhance_mvs_prompt_with_rag
        return await enhance_mvs_prompt_with_rag(user_query, merged)
    except Exception:
        return merged


async def build_code_builder_agent(
    model_id: str,
    api_key: Optional[str] = None,
    *,
    user_query: str = "",
    temperature: float = 0.5,
    max_tokens: int = 2000,
) -> Any:
    """Build a ReAct agent for code generation with RAG-enhanced prompt.

    Tools: SMILES converter, MVS Builder RAG tool.
    """
    llm = get_chat_model(model_id, api_key, temperature=temperature, max_tokens=max_tokens)
    tools = get_tools_for_agent("code_builder")
    system_prompt = await _build_code_builder_prompt(user_query)
    return build_agent_graph(llm, tools, system_prompt=system_prompt)
