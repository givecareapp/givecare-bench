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

The v2 benchmark contract is `gate + quality`: `safety` and `compliance` are fail-closed gates, and `regard` plus `coordination` determine quality only after the gates pass.

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
- Users may generate a leaderboard only from a fresh benchmark-core `leaderboard_ready` export they produced themselves. The repo does not ship pre-made results.

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
uv run python scripts/generate_leaderboard.py --input <your-results>/leaderboard_ready --output data/leaderboard  # input is user-provided
```

Both `bench` and `invisiblebench` follow the agent-friendly CLI standard:
`NO_COLOR=1` is respected, `bench --json` / `--format json` wraps `runs`,
`stats`, and `leaderboard` output in a `{status, command, data}` envelope, and
`invisiblebench --doctor` plus `invisiblebench --list-runs --limit N --offset M`
mirror the paged run index. `--out PATH` (on `runs`, `get`, and `leaderboard
status`) writes the full payload to disk and emits a
`{path, byte_count, record_count}` summary. Live writes (`publish`,
`leaderboard add/rebuild`, `archive`) refuse in non-interactive shells unless
`--yes` is passed.

## Contributing and reporting

- [CONTRIBUTING.md](CONTRIBUTING.md) — dev setup, scenario contract, PR checklist
- [SECURITY.md](SECURITY.md) — private security-advisory channel
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — Contributor Covenant v2.1
- Bugs and feature requests: [GitHub Issues](https://github.com/givecareapp/givecare-bench/issues)
