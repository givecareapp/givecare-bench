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

## Commands

```bash
uv run ruff check .
uv run pytest benchmark/tests -q
uv run bench --help
uv run bench --full --dry-run
python scripts/lint_turn_indices.py --strict
uv run python scripts/generate_leaderboard.py --input <your-results>/leaderboard_ready --output data/leaderboard
```

## Guardrails

- keep `benchmark/` data-only
- keep runtime code in `src/invisiblebench/`
- move historical docs, experiments, and artifacts into `archive/`
- do not reintroduce public confidential scenario files
