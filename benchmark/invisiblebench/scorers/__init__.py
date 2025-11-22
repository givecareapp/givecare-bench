"""Top-level scorers shim for test compatibility.

Re-exports scorer submodules so tests can patch
`invisiblebench.scorers.<dimension>.score`.
"""

from invisiblebench.evaluation.scorers import memory, trauma, belonging, compliance, safety

__all__ = ["memory", "trauma", "belonging", "compliance", "safety"]

