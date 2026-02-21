"""
Shared utilities for agent runner: model ID mapping for OpenRouter.
Used by runner.py and llm/model.py to avoid circular imports.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

try:
    from ..infrastructure.utils import log_line
except ImportError:
    from infrastructure.utils import log_line

_model_map: Dict[str, str] | None = None


def _load_model_map() -> Dict[str, str]:
    """Load model ID mappings from models_config.json.
    Maps legacy Anthropic model IDs to OpenRouter model IDs.
    """
    global _model_map
    if _model_map is not None:
        return _model_map

    _model_map = {}
    config_path = Path(__file__).parent.parent / "models_config.json"
    try:
        if config_path.exists():
            with open(config_path, "r") as f:
                config = json.load(f)
                models = config.get("models", [])
                legacy_to_openrouter = {
                    "claude-3-5-sonnet-20241022": "anthropic/claude-3.5-sonnet",
                    "claude-3-5-sonnet-20240620": "anthropic/claude-3.5-sonnet",
                    "claude-3-opus-20240229": "anthropic/claude-3-opus",
                    "claude-3-sonnet-20240229": "anthropic/claude-3-sonnet",
                    "claude-3-haiku-20240307": "anthropic/claude-3-haiku",
                }
                for model in models:
                    model_id = model.get("id", "")
                    if "/" in model_id:
                        _model_map[model_id] = model_id
                _model_map.update(legacy_to_openrouter)
                log_line("runner:model_map", {"loaded": True, "count": len(_model_map)})
        else:
            log_line("runner:model_map", {"error": "models_config.json not found"})
    except Exception as e:
        log_line("runner:model_map", {"error": str(e)})
        _model_map = {
            "claude-3-5-sonnet-20241022": "anthropic/claude-3.5-sonnet",
            "claude-3-5-sonnet-20240620": "anthropic/claude-3.5-sonnet",
            "claude-3-opus-20240229": "anthropic/claude-3-opus",
            "claude-3-sonnet-20240229": "anthropic/claude-3-sonnet",
            "claude-3-haiku-20240307": "anthropic/claude-3-haiku",
        }

    return _model_map


def map_model_id(model_id: str) -> str:
    """Map legacy model ID to OpenRouter model ID using models_config.json."""
    model_map = _load_model_map()
    return model_map.get(model_id, model_id)
