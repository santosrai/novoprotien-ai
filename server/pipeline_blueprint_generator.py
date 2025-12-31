"""Backward compatibility stub for pipeline_blueprint_generator.py."""

try:
    from .domain.pipeline.blueprint import *
except ImportError:
    from domain.pipeline.blueprint import *
