"""
OpenRouter-backed chat model for LangChain agents.
Single place to build the chat model; no raw HTTP here.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from ..runner_utils import map_model_id

try:
    from langchain.chat_models import init_chat_model
except ImportError:
    init_chat_model = None


def get_chat_model(
    model_id: str,
    api_key: Optional[str] = None,
    *,
    temperature: float = 0.5,
    max_tokens: int = 1000,
) -> Any:
    """Build a LangChain chat model backed by OpenRouter.

    Args:
        model_id: Model ID (legacy or OpenRouter format); will be mapped via models_config.
        api_key: OpenRouter API key; if None, uses OPENROUTER_API_KEY env.

    Returns:
        LangChain chat model (e.g. ChatOpenAI-compatible) for invoke/bind_tools.
    """
    if init_chat_model is None:
        raise RuntimeError("langchain (init_chat_model) is required for LLM agent")
    key = (api_key or os.getenv("OPENROUTER_API_KEY") or "").strip() or None
    openrouter_model = map_model_id(model_id)
    kwargs: dict[str, Any] = {
        "model": openrouter_model,
        "model_provider": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": key,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    return init_chat_model(**kwargs)
