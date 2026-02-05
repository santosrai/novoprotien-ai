"""Backward compatibility stub for pipeline_context.py."""

try:
    from .domain.pipeline.context import *
except ImportError:
    from domain.pipeline.context import *
