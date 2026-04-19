# CLAUDE.md

Primary contributor guide for GiveCare Bench.

## Active structure

- `benchmark/`: public benchmark data and tests
- `src/invisiblebench/`: runtime package
- `scripts/`: active utilities
- `docs/`: active public docs
- `data/leaderboard/`: generated public leaderboard
- `internal/`: active internal workflows, eval tooling, and implementation reference wiki
- `archive/`: historical/internal material

## Current public contract

- benchmark version: `2.1.0`
- public scope: benchmark core only
- public harness: `llm/raw`
- public scenarios: `50`
- branch-bearing files: `22`
- compliance hard fails: diagnosis, patient-specific prescribing/treatment directives, false scope/capability claims
- scenario turn contracts may use `expected_behaviors`, binary `rubric` / `autofail_rubric`, or ordinal `rubric_criteria`
- judge comparability uses stable prompt-template hashes, not fully rendered per-scenario prompt hashes

## Commands

```bash
uv run ruff check .
uv run pytest benchmark/tests -q
uv run bench --help
uv run bench doctor                                 # env + runs_dir precheck
uv run bench --full --dry-run
uv run bench runs --limit 25 --offset 0             # paged run index
uv run bench get <run-id>                           # single run metadata (exact or prefix)
uv run bench --json runs                            # agent-friendly JSON envelope
uv run bench --json runs --out /tmp/runs.json       # write full payload to file; stdout = summary envelope
python scripts/lint_turn_indices.py --strict
uv run python scripts/generate_leaderboard.py --input <your-results>/leaderboard_ready --output data/leaderboard
uv run python scripts/sync_web_bench_leaderboard.py --target /path/to/givecare/apps/web-bench/public/bench/leaderboard.json
uv run python scripts/audit_gold_regard.py --mode llm
uv run python scripts/build_regard_quality_holdout.py
uv run python scripts/build_regard_pairwise_pilot.py
```

## Web-bench delivery

The public benchmark site is now served from a static JSON payload, not a
Convex publish path.

Refresh flow:

```bash
uv run python scripts/generate_leaderboard.py --input <your-results>/leaderboard_ready --output data/leaderboard
uv run python scripts/sync_web_bench_leaderboard.py --target /path/to/givecare/apps/web-bench/public/bench/leaderboard.json
# then deploy web-bench
```

The generated leaderboard metadata now exposes the benchmark's current public
claim surface directly in the JSON: the public hard-fail layer is validated on
60 resolved gold traces, while `overall_score` remains a secondary claim because
`regard` has now been measured against the same gold set and is still not
validation-grade. The internal regard audit now also breaks out a pass-only
slice, and the next calibration phase is scaffolded via `quality_holdout/` and
`regard_pairwise_pilot/` rather than being treated as another prompt-only tweak.

## Agent-friendly CLI

`bench` honors `NO_COLOR=1` and emits `{status, command, data}` JSON on any
subcommand when `--json` / `--format json` is set. `invisiblebench` exposes the
same agent-friendly surface: `--doctor` precheck and `--list-runs --limit N
--offset M`.

**`--out PATH`** (on `runs`, `get`, and `leaderboard status`): writes the full
JSON payload to `PATH` and emits a `{status, command, data: {path, byte_count,
record_count}}` summary envelope on stdout. Use this for large payloads that
would otherwise blow out agent context. Disk-write failures are reported as
`{status:"error", ...}` envelopes, not tracebacks.

**Write-approval gating**: `bench leaderboard add`, `bench leaderboard rebuild`,
and `bench archive`/`clean` refuse in non-interactive shells unless `--yes`
is passed. Reads never prompt.

## Public CI

`.github/workflows/ci.yml` runs `uv run ruff check .`,
`uv run pytest benchmark/tests -q`, and `uv run python
scripts/lint_turn_indices.py --strict` on every push and PR to `main`. The
CI install is `uv sync --extra dev --extra analytics` so any test that
imports numpy/pandas/scipy runs the same as locally.

## Scenario contract

Scenario JSON uses a **`category`** field (not `tier`). Valid values:
`safety`, `empathy`, `context`, `continuity`, `confidential`. The `tier`
field and `tier_0..tier_3` values are rejected by `ScenarioValidator`.
`ScenarioResult` no longer carries a `tier` field; `from_dict` normalizes
legacy `tier` values in old result artifacts to `category` on load.

## Guardrails

- keep `benchmark/` data-only
- keep runtime code in `src/invisiblebench/`
- move historical docs, experiments, and artifacts into `archive/`
- do not reintroduce public confidential scenario files
- treat passive-ideation cues like `wish to be dead` / `wish I could just not wake up` as mental-health crisis triggers; explicit downplay such as `you're exhausted, not suicidal` should fail closed
- structured CBT thought-record templates and explicit patient-specific medication hold/restart instructions are public compliance red lines with regression tests

## Contributor entry points

- `CONTRIBUTING.md` — dev setup, scenario contract, PR checklist
- `SECURITY.md` — private security-advisory channel and disclosure SLA
- `CODE_OF_CONDUCT.md` — points to Contributor Covenant v2.1
- `docs/install.md` — how to put `bench` on PATH from any folder
- `docs/judge-validation.md` — public judge template-hash manifest
- `~/agents/wiki/design-md.md` — global `DESIGN.md` reference and how it should pair with `AGENTS.md`
- `~/agents/wiki/givecare-bench-verifier-implementation.md` — repo-specific verifier implementation reference
- `~/agents/wiki/givecare-bench-autoresearch-implementation.md` — repo-specific autoresearch implementation reference
- `internal/autoresearch/README.md` — autoresearch workflow, runner commands, and merge policy
- `internal/evals/verifier/golden_set/README.md` — calibration-set SOP
- `internal/evals/verifier/golden_set/current_scorer_vs_gold.md` — scorer-vs-gold audit and frozen-run rescore gate
- `internal/evals/verifier/golden_set/annotator_walkthrough.md` — step-by-step annotator tutorial
