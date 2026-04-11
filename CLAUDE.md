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

## Guardrails

- keep `benchmark/` data-only
- keep runtime code in `src/invisiblebench/`
- move historical docs, experiments, and artifacts into `archive/`
- do not reintroduce public confidential scenario files
