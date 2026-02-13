"""Top-level scorer compatibility layer.

v2 exports only safety, compliance, regard, coordination, memory, false_refusal.

# DEPRECATED — v1 compatibility only, do not use in new code.
# Legacy aliases (attunement, belonging, consistency) are kept so that old imports
# like ``from invisiblebench.scorers import attunement`` continue to work.
# New code should import regard, coordination, or memory directly.
"""

import warnings as _warnings

from invisiblebench.evaluation.scorers import (
    compliance,
    coordination,
    false_refusal,
    memory,
    regard,
    safety,
)

# Backward-compatible alias modules — DEPRECATED
attunement = regard
belonging = regard
consistency = memory


def __getattr__(name: str):
    """Emit deprecation warning when legacy scorer aliases are imported."""
    _aliases = {
        "attunement": ("regard", regard),
        "belonging": ("regard", regard),
        "consistency": ("memory", memory),
    }
    if name in _aliases:
        canonical, module = _aliases[name]
        _warnings.warn(
            f"Importing 'invisiblebench.scorers.{name}' is deprecated, "
            f"use 'invisiblebench.scorers.{canonical}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "attunement",
    "belonging",
    "consistency",
    "compliance",
    "coordination",
    "false_refusal",
    "memory",
    "regard",
    "safety",
]
