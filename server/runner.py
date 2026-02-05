"""Backward compatibility stub for runner.py."""

try:
    from .agents.runner import run_agent, run_agent_stream
except ImportError:
    from agents.runner import run_agent, run_agent_stream
