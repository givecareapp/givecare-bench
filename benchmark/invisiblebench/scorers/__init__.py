"""Top-level scorer compatibility layer.

v2 exports only safety, compliance, regard, coordination, memory, false_refusal.
Legacy names are preserved as aliases for backwards-compatible imports.
"""

from invisiblebench.evaluation.scorers import (
    compliance,
    coordination,
    false_refusal,
    memory,
    regard,
    safety,
)

# Backward-compatible alias modules
attunement = regard
belonging = regard
consistency = memory

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
