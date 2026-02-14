# AGENTS.md — GiveCare Bench

## Purpose
Operational guide for contributors and coding agents in this repo.

## Current baseline (v2)
- Scenario organization is **category-based** (MECE): `safety`, `empathy`, `context`, `continuity`, plus `confidential` holdout.
- Do **not** use tier-era paths/flags in new work.
- Standard GiveCare run: **44** scenarios
- With confidential: **47** scenarios

## Source of truth
- Primary project guide: `CLAUDE.md`
- Keep this file short and operational; detailed workflow/examples live in `CLAUDE.md`.

## Core commands
```bash
# Test suite
uv run pytest -q

# Lint
uv run ruff check .

# Model evaluation (raw LLM)
uv run bench --full -y
uv run bench -m deepseek -c safety,empathy -y

# System evaluation (GiveCare/Mira)
uv run bench --provider givecare -y
uv run bench --provider givecare -y --confidential
uv run bench --provider givecare -c safety -y

# Utilities
uv run bench diff <base_run> <new_run>
uv run bench stats results/leaderboard_ready/
uv run bench reliability results/run_YYYYMMDD_HHMMSS/
uv run bench annotate export results/run_YYYYMMDD_HHMMSS/
```

## CLI rules (keep it simple)
1. Prefer explicit flags over magic behavior.
2. Keep one flag = one concept.
3. Use `--category/-c` (not `--tier/-t`).
4. Update `--help` examples when behavior/counts change.
5. Backward compatibility is allowed, but new docs/examples must use canonical v2 terms.

## Guardrails
- Treat `pass`, `fail`, `error` as canonical statuses (`error` counts as failure).
- If scenario set/count changes, update:
  - `benchmark/invisiblebench/cli/runner.py` help text
  - `benchmark/scripts/givecare_provider.py` help/docstrings
  - `CLAUDE.md` and any user-facing docs
- Avoid silent exception swallowing in new code; fail loudly when possible.

## Definition of done
- Tests pass: `uv run pytest -q`
- Lint passes: `uv run ruff check .`
- Help output is aligned: `uv run bench --help`
- No tier-era examples introduced in docs/help for new changes
