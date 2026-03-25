# Solutions Log

Diátaxis: reference

## Run artifacts and diagnostics now accept run directories and per-model outputs

**Date**: 2026-03-12
**Files**: `benchmark/invisiblebench/export/diagnostic.py`, `benchmark/invisiblebench/results_io.py`, `benchmark/invisiblebench/run_artifacts.py`, `benchmark/invisiblebench/run_audit.py`, `benchmark/invisiblebench/cli/leaderboard.py`, `benchmark/invisiblebench/cli/publish.py`

As the benchmark moved from one flat `all_results.json` file to per-model durable artifacts, older tooling still assumed a single aggregate shape. That caused breakage in diagnostics (`'list' object has no attribute 'get'`) and made leaderboard/publish flows too trusting of incomplete or non-audited runs.

**Fix**: Added run-artifact loaders that accept run directories, `model_results/`, or compatibility aggregates; preserved `all_results.json` for backward compatibility; and made `run_audit.json` / `run_audit.md` first-class gating artifacts before leaderboard add, publish, and automatic leaderboard updates.

**Promoted to**: `CLAUDE.md`, `benchmark/scripts/README.md`, `docs/architecture.md`, `docs/methodology.md`
