"""
LangSmith tracing configuration for the agent routing and execution pipeline.

To enable tracing, set these environment variables (in .env or your environment):
  - LANGCHAIN_TRACING_V2=true   (or LANGSMITH_TRACING=true)
  - LANGCHAIN_API_KEY=<key>     (or LANGSMITH_API_KEY=<key>)
  - LANGCHAIN_PROJECT=<name>    (optional; defaults to "novoprotein-agent")

Traces appear at https://smith.langchain.com
"""

import os


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
