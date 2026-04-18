# Solutions Log

Diátaxis: reference

## Codebase cleanup: dead code, slop, legacy tier remnants, weak types, defensive catches

**Date**: 2026-04-15
**Files**: 48 files across `src/invisiblebench/` (-1,287 net lines)

Accumulated cruft from the tier→category migration, AI-generated comments, and broad exception handling. `TierSummary` class and `compute_summaries()` were dead code never called. `ScenarioResult.tier` field, `ResultTiming.tier_seconds`, and `BenchmarkConfig.tiers` were all unused. 10 files had `r.get("category", r.get("tier"))` fallbacks that could be simplified. ~100 restating comments and verbose docstrings added noise. Broad `except Exception` catches hid bugs in 5 locations. 50 mypy errors from weak types and variable shadowing.

**Fix**: removed all dead tier infrastructure (kept `from_dict` normalization for old artifacts). Extracted 5 shared scorer utilities to `_utils.py`. Removed `progress.py` (dead tqdm shim), `IterationTracker`, `MutationAborted`. Narrowed exception catches to specific types (`OSError`, `ImportError`, `SubprocessError`). Removed silent error swallowing in safety scorer. Strengthened types across 10 files (50 mypy errors → 0). Removed ~1,289 lines of slop comments. All 453 tests pass.

## Public-repo polish pass: version reconciled, community-health files added, mkdocs builds strict-clean

**Date**: 2026-04-15  
**Files**: `pyproject.toml`, `src/invisiblebench/__init__.py`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `README.md`, `CLAUDE.md`, `AGENTS.md`, `docs/install.md`, `docs/index.md`, `mkdocs.yml`, `.github/workflows/docs.yml`

`pyproject.toml` said version `1.2.0` while `benchmark/benchmark_card.json` and all public docs said `2.1.0`; the drift would have compounded in any CHANGELOG work. README had no badges, no docs-site link, and no pointer to contributor material. No `CONTRIBUTING.md`, `SECURITY.md`, or `CODE_OF_CONDUCT.md` existed. `mkdocs build` emitted warnings: `docs/install.md` linked to `../CLAUDE.md` (not a docs page), and `docs/_solutions.md` + `docs/rescored-benchmark-summary-2026-03-31.md` were orphaned from nav. `.github/workflows/docs.yml` used raw `pip`, inconsistent with the rest of the repo's uv tooling.

**Fix**: bumped `pyproject.toml` and `src/invisiblebench/__init__.py` to 2.1.0; added CI/License/Docs badges + docs-site link in README; wrote CONTRIBUTING (dev setup, scenario contract, PR checklist), SECURITY (private-advisory + ali@scty.org with 7-day SLA), and a short CODE_OF_CONDUCT pointing to Contributor Covenant v2.1; inlined the Convex `--prod` gotcha into `docs/install.md`; added `not_in_nav:` entries in `mkdocs.yml`; rewrote `docs.yml` to use uv + `mkdocs-material`. `mkdocs build --strict` now passes clean.

## Scenario contract is now category-only; legacy `tier` field and `tier_0..tier_3` values are rejected

**Date**: 2026-04-15  
**Files**: `benchmark/scenarios/**/*.json` (50 files), `src/invisiblebench/loaders/scenario_loader.py`, `src/invisiblebench/models/scenario.py`, `src/invisiblebench/models/__init__.py`, `src/invisiblebench/models/results.py`, `src/invisiblebench/stats/analysis.py`, `src/invisiblebench/results_io.py`, `benchmark/tests/unit/test_contract_drift.py`, `benchmark/tests/unit/test_loaders.py`, `benchmark/tests/unit/test_scenario_validator.py`, `benchmark/tests/unit/test_scenario_models.py`, `benchmark/tests/unit/test_orchestrator_hard_fails.py`

The scenario schema, the Pydantic `ScenarioModel`, and the legacy `Scenario` dataclass each encoded the `tier` → `category` migration differently: `tier` was marked deprecated in Pydantic, but the validator accepted either field and even accepted legacy `tier_0..tier_3` values. The legacy `Scenario` dataclass also had `category: Optional[DimensionType]`, which mistyped a category-level field as a sub-dimension. External reviewers flagged this as unfinished contract drift.

**Fix**: migrated all 50 public scenario JSONs to `category` only, hardened `ScenarioValidator` to reject the `tier` field and `tier_N` values, made `category` a required field on `ScenarioModel` and the legacy `Scenario` dataclass, removed `tier_number` and `TierLevel`, renamed `load_by_tier` → `load_by_category`, and added `test_no_legacy_tier_field` to lock the corpus. `ScenarioResult.tier` was subsequently removed; `from_dict` still normalizes legacy `tier` values to `category` on load.

## bench live writes gate on `confirm_or_abort`, and `--out PATH` exports large payloads to disk

**Date**: 2026-04-15  
**Files**: `src/invisiblebench/cli/runner.py`, `benchmark/tests/unit/test_cli_flags.py`

The agent-friendly CLI guarantees in `~/agents/_rules/general/cli.md` require (a) that large payloads be writable to a file instead of blown inline, and (b) that live writes refuse in non-interactive shells unless explicitly approved. `bench runs`, `bench get`, and `bench --json leaderboard status` were inlining full payloads; `bench publish`, `bench leaderboard add/rebuild`, and `bench archive` had no interactive gate.

**Fix**: added `--out PATH` (runs/get/leaderboard-status) writing the full payload and emitting a `{status, command, data:{path, byte_count, record_count}}` summary envelope, with `OSError` caught and reported via error envelope rather than traceback. Wired `confirm_or_abort` into the dispatch paths for publish / leaderboard add|rebuild / archive; `--yes` bypasses, reads never prompt. `archive` without `--before` or `--keep` now exits 2 with a clear error instead of prompting with `(before=None, keep=None)`. Coverage in `test_cli_flags.py` (9 tests).

## Scoring comparability now uses prompt-template hashes, and scenario rubric contracts are fully supported

**Date**: 2026-03-29  
**Files**: `src/invisiblebench/api/client.py`, `src/invisiblebench/evaluation/scorers/{safety,compliance,regard,coordination,rubric_scorer}.py`, `src/invisiblebench/models/{__init__,scenario}.py`, `src/invisiblebench/loaders/scenario_loader.py`, `benchmark/configs/scoring.yaml`, `benchmark/configs/prompts/compliance_framework.txt`, `benchmark/scenarios/SCENARIO_SCHEMA.yaml`

Run audit comparability was incorrectly using hashes of fully rendered judge prompts, which made scenario-specific prompt content look like contract drift. At the same time, the scenario contract had drifted: `rubric` / `autofail_rubric` were authored in scenario JSON, but typed models and rubric scoring only partially supported them, and ordinal `rubric_criteria` were being flattened into binary behavior.

**Fix**: judge metadata now stores stable prompt-template hashes for comparability; the compliance contract explicitly hard-fails false scope/capability claims and preserves allowed practical caregiving support plus general public medication information; scenario models and validation now preserve `rubric`, `autofail_rubric`, and ordinal `rubric_criteria`; and the rubric scorer now handles ordinal criteria with partial credit instead of silently degrading them.
