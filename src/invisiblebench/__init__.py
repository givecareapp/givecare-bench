"""InvisibleBench - AI safety benchmark for long-term caregiving relationships.

V3 scoring uses the ModeEngine verifier pattern.
Score transcripts via: uv run python scripts/run_scan.py
"""

from invisiblebench.version import BENCHMARK_VERSION, RESULT_CONTRACT_VERSION

__version__ = BENCHMARK_VERSION

__all__ = ["BENCHMARK_VERSION", "RESULT_CONTRACT_VERSION", "__version__"]
