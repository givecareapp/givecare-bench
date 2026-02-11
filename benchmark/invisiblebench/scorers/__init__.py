"""Top-level scorers shim for test compatibility.

Re-exports scorer submodules so tests can patch
`invisiblebench.scorers.<dimension>.score`.
"""

from invisiblebench.evaluation.scorers import (
    attunement,
    belonging,
    compliance,
    consistency,
    false_refusal,
    memory,
    safety,
)

__all__ = [
    "memory",
    "attunement",
    "belonging",
    "compliance",
    "safety",
    "consistency",
    "false_refusal",
]
