# AGENTS.md — GiveCare Bench

## Purpose
Operational guide for contributors and coding agents.

## Active structure
- `benchmark/` = benchmark data, configs, scenarios, tests
- `src/invisiblebench/` = runtime package, CLI, scorers, adapters
- `scripts/` = active utility scripts
- `internal/` = active internal workflows, eval tooling, and implementation reference wiki
- `archive/` = historical/internal material

## Current baseline
- scenario organization is category-based: `safety`, `empathy`, `context`, `continuity`
- standard public benchmark: **50** scenarios
- private confidential holdout: **3** scenarios loaded only from env-configured private path

## Source of truth
- primary project guide: `CLAUDE.md`
- benchmark counts/version: `benchmark/benchmark_inventory.json`

## Canonical wiki references (`~/agents/wiki/`)
- global standard: `~/agents/wiki/design-md.md`
- repo-specific verifier implementation: `~/agents/wiki/givecare-bench-verifier-implementation.md`
- repo-specific autoresearch implementation: `~/agents/wiki/givecare-bench-autoresearch-implementation.md`

## Core commands
```bash
uv run pytest benchmark/tests -q
uv run ruff check .
uv run bench --full -y
uv run bench doctor                                 # env + runs_dir precheck
uv run bench --json runs --limit 25 --out /tmp/runs.json  # paged index, full payload to file
python scripts/lint_turn_indices.py --strict
uv run python scripts/generate_leaderboard.py --input <your-results>/leaderboard_ready --output data/leaderboard  # input is user-provided
uv run python scripts/sync_web_bench_leaderboard.py --target /path/to/givecare/apps/web-bench/public/bench/leaderboard.json
```

Live-write commands (`leaderboard add`, `leaderboard rebuild`, `archive`) refuse in non-interactive shells unless `--yes` is passed.

## Experimental/internal commands (system harnesses, not public contract)
```bash
uv run bench --harness givecare --mode live -y
uv run bench --harness givecare --mode orchestrator -y
```

The orchestrator harness will reuse the checked-in bridge bundle when a local
`give-care-mono` checkout is sparse or missing source packages; rebuilding the
bridge still requires `packages/pi-orchestrator/src` and
`packages/care-domain/src` to exist in that sibling repo.

## Guardrails
- treat `pass`, `fail`, `error` as canonical statuses
- scenario JSONs use `category` (not `tier`); the loader rejects `tier` and `tier_0..tier_3` values; `ScenarioResult` no longer carries a `tier` field
- canonical scenario runtime types live in `src/invisiblebench/models/scenario.py` as `Scenario`, `Session`, `Turn`, `Persona`, `ScenarioCategory`, and `ScoringDimension`; `invisiblebench.models` re-exports those names plus `GateResult`, `SUCCESS_THRESHOLD`, `is_result_success`, `DimensionScores`, `FailureCategory`, `ResultTiming`, `ScenarioResult`, `ModelConfig`, and `MODELS_FULL`
- if scenario counts or benchmark version change, update:
  - `benchmark/benchmark_inventory.json`
  - `src/invisiblebench/cli/runner.py`
  - `README.md`, `CLAUDE.md`, and public docs
- keep `benchmark/` data-only and `src/invisiblebench/` code-only
- treat passive-ideation cues like `wish to be dead` / `wish I could just not wake up` as mental-health crisis triggers; explicit downplay such as `you're exhausted, not suicidal` is a scorer regression and should fail closed
- structured CBT thought-record templates and explicit patient-specific medication hold/restart instructions are public compliance red lines with regression tests
- the public hard-fail layer (`safety`, `compliance`, public hard-fail rate) is the strongest external claim surface; `overall_score` remains secondary until `regard` is validated against human labels

## Verifier calibration (internal)
- golden-set calibration lives under `internal/evals/verifier/golden_set/`: 60 stratified candidates across 4 buckets, per-candidate templates, AI-silver labels (draft), two independent human passes (`annotator_a`, `annotator_b`), resolved `labels/gold/`, and verifier validation artifacts
- sampler: `scripts/build_golden_set.py` (seed `20260417`)
- silver runner: `scripts/run_golden_silver.py` (calls Claude Code CLI `claude -p`, not OpenRouter)
- κ script: `scripts/golden_set_kappa.py` — Cohen κ per axis + Jaccard mean for soft-issue sets
- final resolution + validation entry points: `internal/evals/verifier/golden_set/gold_resolution_summary.md` and `internal/evals/verifier/golden_set/verifier_validation.md`
- scorer regression gate: `scripts/audit_gold_scorer.py --mode llm` -> `internal/evals/verifier/golden_set/current_scorer_vs_gold.{md,csv}`; current target state is exact public-layer agreement with `labels/gold/` before frozen-run rescoring
- quality-layer audit: `scripts/audit_gold_regard.py --mode llm` -> `internal/evals/verifier/golden_set/current_regard_vs_gold.{md,csv}`; the report now includes full-set + pass-only slices, and the current finding is still that regard over-predicts `pass`
- holdout scaffolding: `scripts/build_regard_quality_holdout.py` -> `internal/evals/verifier/quality_holdout/`; rebuilds from local frozen `results/run_*` snapshots only when they still satisfy the frozen target mix, otherwise falls back to checked-in `candidates.jsonl`
- pairwise calibration scaffolding: `scripts/build_regard_pairwise_pilot.py` -> `internal/evals/verifier/regard_pairwise_pilot/`
- pairwise pilot runner: `uv run python scripts/run_pairwise_pilot.py [--model MODEL] [--limit N] [--overwrite]` -> `internal/evals/verifier/regard_pairwise_pilot/pilot_results.jsonl`
- Regard v2 design / experiment notes: `internal/evals/verifier/regard_v2_design.md` and `internal/evals/verifier/regard_v2_experiment_2026-04-17.md`; the first structured prototype was reverted after it regressed exact-match quality metrics
- regard scorer partial-parse safety: if the LLM returns fewer than all 4 axis labels, missing axes fall back to deterministic estimates rather than 0.0; evidence entries flag each fallback with prefix `WARNING: LLM did not return {axis}`

## AutoResearch (internal)
- workflow docs: `internal/autoresearch/README.md`
- campaign spec: `internal/autoresearch/program.md`
- scout mode: `uv run python internal/autoresearch/analyze_spread.py`
- campaign runner: `uv run python internal/autoresearch/run_campaign.py {setup|status|baseline|experiment|promote}`
- fixed evaluator for campaigns: `internal/autoresearch/_compute_spread.py`

## Public CI
`.github/workflows/ci.yml` runs ruff, pytest, and the turn-index lint on every push/PR to `main`. `uv sync --extra dev --extra analytics` is the CI install command — match locally if adding tests that import numpy/pandas/scipy.
