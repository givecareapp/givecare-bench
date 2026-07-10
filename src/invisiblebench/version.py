"""Single source of truth for InvisibleBench version constants.

This is a leaf module with no intra-package imports so it can be imported
from anywhere (models, cli, scripts) without circular-import risk.

- ``BENCHMARK_VERSION`` — the public benchmark corpus/checks version. It must
  match ``benchmark/benchmark_inventory.json``'s ``benchmark_version`` and the
  generated leaderboard metadata. The canonical machine-readable source for
  runtime reads is the inventory (see ``utils.benchmark_inventory``); this
  constant is the in-code mirror used for display and result stamping.
Result rows carry one of two schema versions, by design:

- ``RESULT_CONTRACT_VERSION`` (2.1.0) — the v2.1 judge-metadata result-row
  schema. Stamped on the ``ScenarioResult`` model default, error rows, and the
  scoring-summary fallback.
- ``SCANNED_ROW_CONTRACT_VERSION`` (3.2.0) — the ModeEngine scanned-row schema,
  stamped on rows produced by the per-check scoring adapter.

Both are deliberately distinct from ``BENCHMARK_VERSION`` (the corpus/checks
version): result-row schemas and the benchmark corpus evolve independently.
These constants name the two contract versions in one place rather than
scattering them as string literals across the runner.
"""

from __future__ import annotations

BENCHMARK_VERSION = "4.0.0"
RESULT_CONTRACT_VERSION = "2.1.0"
SCANNED_ROW_CONTRACT_VERSION = "3.2.0"

__all__ = [
    "ENGINE_VERSION",
    "BENCHMARK_VERSION",
    "RESULT_CONTRACT_VERSION",
    "SCANNED_ROW_CONTRACT_VERSION",
]

# Mode-engine aggregator version, stamped on ModeEngineOutput rows and on
# engine-emitted verdicts (unrouted / verifier-exception paths).
ENGINE_VERSION = "v0.1"
