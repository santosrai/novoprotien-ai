"""Backward compatibility stub for pipeline_schema.py."""

try:
    from .domain.pipeline.schema import *
except ImportError:
    from domain.pipeline.schema import *
