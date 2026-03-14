"""LangChain tool: MVS Builder – retrieve MolViewSpec examples via RAG."""

from __future__ import annotations

import json

try:
    from langchain_core.tools import tool
except ImportError:
    tool = None


def get_mvs_builder_tool():
    """Return a LangChain tool that retrieves MVS code examples via RAG.

    When called by an agent, this tool queries the Pinecone RAG index for
    MolViewSpec examples matching the user's visualization intent and returns
    them so the LLM can generate correct MVS code.
    """
    if tool is None:
        raise RuntimeError("langchain_core.tools is required")

    @tool
    async def mvs_builder(query: str) -> str:
        """Retrieve MolViewSpec code examples relevant to a visualization request.
        Use when the user asks to visualize, show, display, or render a molecular
        structure and you need MolViewSpec API examples to generate the code.

        Args:
            query: The user's visualization intent (e.g. 'show cartoon with surface',
                   'label binding site residues', 'color by chain').
        """
        try:
            try:
                from ...memory.rag.mvs_rag import get_rag_retriever
            except ImportError:
                from memory.rag.mvs_rag import get_rag_retriever
            retriever = await get_rag_retriever()
            examples = []
            if retriever:
                examples = await retriever.retrieve_relevant_examples(query)
            if examples:
                return json.dumps({"examples": examples})
            return json.dumps({"examples": [], "note": "No RAG examples found; use base MVS API knowledge."})
        except Exception as e:
            return json.dumps({"examples": [], "error": str(e)})

    return mvs_builder
