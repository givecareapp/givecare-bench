# CLAUDE.md

Primary contributor guide for GiveCare Bench.

## Active structure

- `benchmark/`: public benchmark data and tests
- `src/invisiblebench/`: runtime package
- `scripts/`: active utilities
- `docs/`: active public docs
- `data/leaderboard/`: generated public leaderboard
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
```

## Publishing to Convex

Publish the rescored leaderboard to the **prod** Convex deployment (`doting-tortoise-411`):

```bash
uv run bench publish results/leaderboard_ready
```

Requires two env vars in `.env`:
- `CONVEX_SITE_URL=https://doting-tortoise-411.convex.site`
- `BENCH_PUBLISH_KEY` — get from: `cd ~/projects/givecare/apps/data-agent && npx convex env get BENCH_PUBLISH_KEY --prod`

The Convex endpoint is `POST /api/bench/publish` in `givecare/apps/data-agent/convex/bench/publish.ts`.

### Convex --prod gotcha

`npx convex env` defaults to **dev** (`agreeable-lion-831`), not prod. Always pass `--prod` when reading/writing prod env vars. The `CONVEX_DEPLOYMENT=prod:slug` env override is unreliable — use the `--prod` flag.

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

**Write-approval gating**: `bench publish`, `bench leaderboard add`,
`bench leaderboard rebuild`, and `bench archive`/`clean` refuse in
non-interactive shells unless `--yes` is passed. Reads never prompt.

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

## Contributor entry points

- `CONTRIBUTING.md` — dev setup, scenario contract, PR checklist
- `SECURITY.md` — private security-advisory channel and disclosure SLA
- `CODE_OF_CONDUCT.md` — points to Contributor Covenant v2.1
- `docs/install.md` — how to put `bench` on PATH from any folder
- `docs/judge-validation.md` — public judge template-hash manifest
- `internal/wiki/README.md` — internal implementation wiki index
- `internal/wiki/llm-as-a-verifier.md` — upstream verifier reference + local adaptation
- `internal/wiki/autoresearch.md` — upstream autoresearch reference + local adaptation
- `internal/evals/verifier/golden_set/README.md` — calibration-set SOP
- `internal/evals/verifier/golden_set/annotator_walkthrough.md` — step-by-step annotator tutorial
