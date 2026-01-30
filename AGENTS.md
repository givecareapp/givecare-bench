# Repository Guidelines

## Structure
Core: `benchmark/invisiblebench/` | Scenarios: `benchmark/scenarios/tier{0-3}/` | Tests: `benchmark/tests/` | Papers: `papers/`

## Commands

```bash
# Benchmark (primary: uv run bench)
uv run bench --minimal -y              # 1 model (~$0.05)
uv run bench --full -y                 # 11 models (~$5-10)
uv run bench --full -m 1-4 -y          # Models 1-4 only
uv run bench --full -m 4 -t 3 -y       # Model 4, tier 3
uv run bench --full -m 1-4 -p 4 -y     # 4 parallel
uv run bench --dry-run                 # Cost estimate

# Rerun specific model
uv run bench --full -m 2 -y --update-leaderboard   # Rerun GPT-5.2

# Models: 1=Opus4.5 2=GPT-5.2 3=Gemini3Pro 4=Sonnet4.5 5=Grok4
#         6=GPT-5Mini 7=DeepSeekV3.2 8=Gemini2.5Flash 9=MiniMaxM2.1 10=Qwen3-235B
#         11=KimiK2.5

# Health & Maintenance
uv run bench health                    # Check leaderboard for issues
uv run bench runs                      # List all benchmark runs
uv run bench archive                   # Archive runs before today
uv run bench archive --keep 5          # Keep only 5 most recent

# Tests & Quality
pytest benchmark/tests/ -v
mypy benchmark/invisiblebench/ && ruff check benchmark && black benchmark
```

## Results

- Active: `results/run_*/` | Archived: `results/archive/`
- `bench health` flags: errors, missing scenarios, suspect scenarios (failing on 3+ models)
- `bench archive` cleans up old runs

## Style
- Black-formatted, 100-char lines, type hints for new code
- Tests: `test_*.py`, fixtures in `benchmark/tests/fixtures/`
- Status values: `pass`, `fail`, `error` (treat `error` as failure)

## Session End (MANDATORY)
1. Run quality gates if code changed
2. `git pull --rebase && git push` - Work NOT complete until push succeeds
3. Never stop before pushing
