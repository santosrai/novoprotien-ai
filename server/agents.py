"""Backward compatibility stub for agents.py."""

try:
    from .agents.registry import agents, list_agents
except ImportError:
    from agents.registry import agents, list_agents
