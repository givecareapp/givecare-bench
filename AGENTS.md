# AGENTS.md — GiveCare Bench

## Purpose
Operational guide for contributors and coding agents.

## Active structure
- `benchmark/` = benchmark data, configs, scenarios, tests
- `src/invisiblebench/` = runtime package, CLI, scorers, adapters
- `scripts/` = active utility scripts
- `archive/` = historical/internal material

## Current baseline
- scenario organization is category-based: `safety`, `empathy`, `context`, `continuity`
- standard public benchmark: **50** scenarios
- private confidential holdout: **3** scenarios loaded only from env-configured private path

## Source of truth
- primary project guide: `CLAUDE.md`
- benchmark counts/version: `benchmark/benchmark_inventory.json`

## Core commands
```bash
uv run pytest benchmark/tests -q
uv run ruff check .
uv run bench --full -y
uv run bench doctor                                 # env + runs_dir precheck
uv run bench --json runs --limit 25 --out /tmp/runs.json  # paged index, full payload to file
python scripts/lint_turn_indices.py --strict
uv run python scripts/generate_leaderboard.py --input <your-results>/leaderboard_ready --output data/leaderboard  # input is user-provided
```

Live-write commands (`publish`, `leaderboard add`, `leaderboard rebuild`, `archive`) refuse in non-interactive shells unless `--yes` is passed.

## Experimental/internal commands (system harnesses, not public contract)
```bash
uv run bench --harness givecare --mode live -y
uv run bench --harness givecare --mode orchestrator -y
```

## Guardrails
- treat `pass`, `fail`, `error` as canonical statuses
- scenario JSONs use `category` (not `tier`); the loader rejects `tier` and `tier_0..tier_3` values; `ScenarioResult` no longer carries a `tier` field
- if scenario counts or benchmark version change, update:
  - `benchmark/benchmark_inventory.json`
  - `src/invisiblebench/cli/runner.py`
  - `README.md`, `CLAUDE.md`, and public docs
- keep `benchmark/` data-only and `src/invisiblebench/` code-only

## Public CI
`.github/workflows/ci.yml` runs ruff, pytest, and the turn-index lint on every push/PR to `main`. `uv sync --extra dev --extra analytics` is the CI install command — match locally if adding tests that import numpy/pandas/scipy.
