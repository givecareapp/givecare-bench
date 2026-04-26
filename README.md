# GiveCare Bench

[![CI](https://github.com/givecareapp/givecare-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/givecareapp/givecare-bench/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-mkdocs--material-blue)](https://givecareapp.github.io/givecare-bench)

GiveCare Bench is a standalone public benchmark for multi-turn caregiver-support AI.

Full docs: [givecareapp.github.io/givecare-bench](https://givecareapp.github.io/givecare-bench).

The repo is organized around three buckets:
- public benchmark surfaces
- active internal evaluation surfaces
- archived historical material

The benchmark uses a gate-then-quality architecture. Safety (A) and compliance (B) are fail-closed gates -- any failure zeroes the score. Three quality dimensions -- communication (C), coordination (D), and boundary integrity (F) -- measure how the model speaks, what it does next, and how honestly it represents itself. 48 per-check verifiers across these 5 dimensions are calibrated against human expert labels. See [Taxonomy](docs/taxonomy.md) for the full framework.

## Public, internal, and historical

### Public
These are the parts external users should rely on:
- `benchmark/`: public benchmark data, configs, schemas, tests
- `src/invisiblebench/`: runtime package, scoring, CLI, adapters
- `scripts/`: active maintenance utilities
- `docs/`: public docs
- `data/leaderboard/`: generated public leaderboard artifact
- `adapters/`: external bridge assets used by experimental/internal harnesses

### Internal-active
These are versioned in the repo, but they are not part of the public benchmark contract:
- `internal/autoresearch/`: scenario optimization campaigns and spread analysis
- `internal/evals/`: judge analysis, labeling, and scorer validation work
- `internal/papers/`: paper source and research artifacts

### Historical
These are retained for provenance, not day-to-day use:
- `archive/benchmark/`
- `archive/docs/`
- `archive/internal/`
- `archive/scenarios/`
- `archive/scripts/`

## Active repo shape

```text
givecare-bench/
├── benchmark/            # public corpus, configs, contract, tests
├── src/invisiblebench/   # runtime package
├── scripts/              # active repo utilities
├── docs/                 # public documentation
├── data/leaderboard/     # generated public artifacts
├── internal/             # active non-public workflows
│   ├── autoresearch/
│   ├── evals/
│   └── papers/
├── archive/              # historical material only
└── adapters/             # external bridge assets
```

## Public release policy

- Public leaderboard scope is benchmark-core only.
- Publicly comparable runs use the raw `llm` surface.
- GiveCare live and orchestrator harnesses remain experimental/internal.
- Private confidential scenarios are loaded externally and are not stored in this repo.
- The public leaderboard artifact is `data/leaderboard/leaderboard.json`, mirrored into `apps/web-bench/public/bench/leaderboard.json` in the web repo and QA-gated with `scripts/qa_leaderboard.py --strict`.
- Leaderboard metadata carries a machine-readable claim surface and validation summary: the public hard-fail layer (`safety`, `compliance`, public hard-fail rate) is calibrated on the resolved 60-trace gold set; quality-mode verdicts are complete for the frozen transcript artifact but should still be described more cautiously than public gates.

## Core commands

```bash
uv run pytest benchmark/tests -q
uv run ruff check .
uv run bench --help
uv run bench doctor                                 # validate env vars + runs dir
uv run bench --full --dry-run
uv run bench runs --limit 25 --offset 0             # list runs (paged)
uv run bench get <run-id>                           # read a single run's metadata
uv run bench --json runs                            # JSON envelope for agents
uv run bench --json runs --out /tmp/runs.json       # write full payload to file; stdout = summary envelope
python scripts/lint_turn_indices.py --strict
uv run python scripts/run_scan.py results/run_... results/partial_runs/... --enable-llm  # ModeEngine scan; costs tokens
uv run python scripts/generate_leaderboard.py --input <scan>/per_run.jsonl --output data/leaderboard
uv run python scripts/qa_leaderboard.py --scan <scan>/per_run.jsonl --leaderboard data/leaderboard/leaderboard.json --manual-adjudications <scan>/manual_adjudications.json --strict
uv run python scripts/sync_web_bench_leaderboard.py --source data/leaderboard/leaderboard.json --target /path/to/givecare/apps/web-bench/public/bench/leaderboard.json
```

Both `bench` and `invisiblebench` follow the agent-friendly CLI standard:
`NO_COLOR=1` is respected, `bench --json` / `--format json` wraps `runs`,
`stats`, and `leaderboard` output in a `{status, command, data}` envelope, and
`invisiblebench --doctor` plus `invisiblebench --list-runs --limit N --offset M`
mirror the paged run index. `--out PATH` (on `runs`, `get`, and `leaderboard
status`) writes the full payload to disk and emits a
`{path, byte_count, record_count}` summary. Live writes (`leaderboard
add/rebuild`, `archive`) refuse in non-interactive shells unless `--yes` is
passed.

## Contributing and reporting

- [CONTRIBUTING.md](CONTRIBUTING.md) — dev setup, scenario contract, PR checklist
- [SECURITY.md](SECURITY.md) — private security-advisory channel
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — Contributor Covenant v2.1
- Bugs and feature requests: [GitHub Issues](https://github.com/givecareapp/givecare-bench/issues)
