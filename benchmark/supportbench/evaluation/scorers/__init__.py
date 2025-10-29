"""Scoring modules for different evaluation dimensions.

This package exposes submodules that each provide a `score(...)`
function returning a structured result for that dimension.
"""

# Expose submodules for direct import in orchestrator and tests
__all__ = [
    "memory",
    "trauma",
    "belonging",
    "compliance",
    "safety",
]
