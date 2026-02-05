"""Backward compatibility stub for router_graph.py."""

try:
    from .agents.router import init_router, routerGraph, SimpleRouterGraph
except ImportError:
    from agents.router import init_router, routerGraph, SimpleRouterGraph
