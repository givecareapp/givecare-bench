# Repository Guidelines

## Structure
Core: `benchmark/invisiblebench/` | Scenarios: `benchmark/scenarios/tier{1-3}/` | Tests: `benchmark/tests/` | Papers: `papers/`

## Commands

```bash
# Benchmark (primary: uv run bench)
uv run bench --full -y                 # All 12 models (~$5-10)
uv run bench -m deepseek -y            # Single model by name
uv run bench -m gpt-5.2,claude -y      # Multiple models by name
uv run bench -m 1-4 -y                 # Models 1-4 (backward compat)
uv run bench -m 4 -t 3 -y             # Model 4, tier 3
uv run bench -m 1-4 -p 4 -y           # 4 parallel
uv run bench --dry-run                 # Cost estimate + model catalog

# Rerun specific model
uv run bench -m gpt-5.2 -y --update-leaderboard   # Rerun GPT-5.2

# Models: 1=Opus4.5 2=GPT-5.2 3=Gemini3Pro 4=Sonnet4.5 5=Grok4
#         6=GPT-5Mini 7=DeepSeekV3.2 8=Gemini2.5Flash 9=MiniMaxM2.1 10=Qwen3-235B
#         11=KimiK2.5 12=Opus4.6
# -m accepts names (partial, case-insensitive) or numbers

# Health & Maintenance
uv run bench health                    # Check leaderboard for issues
uv run bench runs                      # List all benchmark runs
uv run bench archive                   # Archive runs before today
uv run bench archive --keep 5          # Keep only 5 most recent

# Tests & Quality
pytest benchmark/tests/ -v
mypy benchmark/invisiblebench/ && ruff check benchmark && black benchmark
```

## GiveCare Provider

```bash
uv run bench --provider givecare -y                    # Standard (29 scenarios)
uv run bench --provider givecare -y --confidential     # Full (32 scenarios)
uv run bench --provider givecare -y --diagnose         # With diagnostic report
```

## Results

- Active: `results/run_*/` | Archived: `results/archive/`
- `bench health` flags: errors, missing scenarios, suspect scenarios (failing on 3+ models)
- `bench archive` cleans up old runs

## Style
- Black-formatted, 100-char lines, type hints for new code
- Tests: `test_*.py`, fixtures in `benchmark/tests/fixtures/`
- Status values: `pass`, `fail`, `error` (treat `error` as failure)

## Conditional Branching

5 scenarios have adaptive branches — user messages change based on model behavior:
- Automatic (no CLI flags), works in both model eval and system eval
- Branch conditions: `contains_any`, `contains_all`, `not_contains`, `regex`
- Branch IDs in transcript JSONL for audit
- Module: `evaluation/branching.py` | Tests: `tests/unit/test_branching.py` (20 tests)

## Scorer Cache

Scorer LLM calls (temp=0) are cached via LRU in `api/client.py`:
- Configure: `INVISIBLEBENCH_SCORER_CACHE_SIZE=256` (default, 0 to disable)
- Applies to: belonging, safety, attunement, false_refusal scorers with `use_cache=True`

## Session End (MANDATORY)
1. Run quality gates if code changed
2. `git pull --rebase && git push` - Work NOT complete until push succeeds
3. Never stop before pushing
