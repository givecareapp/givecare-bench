"""InvisibleBench - AI safety benchmark for long-term caregiving relationships.

Safety/Care observations are derived from the retained judgment ledger.
Score transcripts via: uv run python scripts/run_scan.py
"""

from invisiblebench.version import (
    BENCHMARK_VERSION,
)

__version__ = BENCHMARK_VERSION

__all__ = [
    "BENCHMARK_VERSION",
    "__version__",
]
