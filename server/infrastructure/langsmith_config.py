"""
LangSmith tracing configuration for the agent routing and execution pipeline.

To enable tracing, set these environment variables (in .env or your environment):
  - LANGCHAIN_TRACING_V2=true   (or LANGSMITH_TRACING=true)
  - LANGCHAIN_API_KEY=<key>     (or LANGSMITH_API_KEY=<key>)
  - LANGCHAIN_PROJECT=<name>    (optional; defaults to "novoprotein-agent")

Traces appear at https://smith.langchain.com
"""

import os
from contextlib import nullcontext
from typing import Any, Dict, Optional

try:
    from langsmith import tracing_context, Client as LangSmithClient
except ImportError:
    tracing_context = None
    LangSmithClient = None


def _is_tracing_enabled() -> bool:
    """Check if LangSmith tracing is enabled via environment."""
    v2 = os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1", "yes")
    smith = os.getenv("LANGSMITH_TRACING", "").lower() in ("true", "1", "yes")
    return v2 or smith


def _ensure_project() -> None:
    """Set default project if not configured."""
    if not os.getenv("LANGCHAIN_PROJECT") and not os.getenv("LANGSMITH_PROJECT"):
        os.environ["LANGCHAIN_PROJECT"] = "novoprotein-agent"


def setup_langsmith() -> bool:
    """
    Configure LangSmith tracing. Call early at app startup (after env load).
    Returns True if tracing is enabled, False otherwise.
    """
    _ensure_project()
    enabled = _is_tracing_enabled()
    if enabled:
        api_key = os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY")
        project = os.getenv("LANGCHAIN_PROJECT") or os.getenv("LANGSMITH_PROJECT")
        if api_key:
            print(f"[LangSmith] Tracing enabled → project: {project}")
        else:
            print("[LangSmith] Tracing requested but LANGCHAIN_API_KEY/LANGSMITH_API_KEY not set")
    return enabled


def langsmith_context(langsmith_config: Optional[Dict[str, Any]]):
    """
    Return a context manager for LangSmith tracing based on user settings.
    - enabled=False: explicitly disable tracing
    - enabled=True + apiKey: use user's LangSmith client
    - enabled=True, no apiKey: use env (no-op context, default behavior)
    - no config: use env (no-op context)
    """
    if tracing_context is None:
        return nullcontext()

    cfg = langsmith_config or {}
    enabled = cfg.get("enabled", True)

    if enabled is False:
        return tracing_context(enabled=False)

    api_key = (cfg.get("apiKey") or "").strip()
    if api_key and LangSmithClient:
        project = cfg.get("project") or "novoprotein-agent"
        client = LangSmithClient(
            api_key=api_key,
            api_url="https://api.smith.langchain.com",
        )
        return tracing_context(client=client, project_name=project)

    return nullcontext()
