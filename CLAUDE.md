# CLAUDE.md

Research benchmark project. Say "done" when finished (no verbose summaries).

## CLI

```bash
# Benchmark (primary: uv run bench)
uv run bench --minimal -y              # 1 model (~$0.05)
uv run bench --full -y                 # 11 models (~$5-10)
uv run bench --full -m 1-4 -y          # Models 1-4 only
uv run bench --full -m 4 -t 3 -y       # Model 4, tier 3
uv run bench --full -m 1-4 -p 4 -y     # 4 parallel
uv run bench --dry-run                 # Cost estimate
uv run bench --minimal -y --detailed   # Per-scenario JSON/HTML

# Rerun specific model (use after errors)
uv run bench --full -m 2 -y --update-leaderboard   # Rerun GPT-5.2

# Models: 1=Opus4.5 2=GPT-5.2 3=Gemini3Pro 4=Sonnet4.5 5=Grok4
#         6=GPT-5Mini 7=DeepSeekV3.2 8=Gemini2.5Flash 9=MiniMaxM2.1 10=Qwen3-235B
#         11=KimiK2.5

# Health & Maintenance
uv run bench health                    # Check leaderboard for issues
uv run bench health -v                 # Verbose (show failed scenarios)
uv run bench runs                      # List all benchmark runs
uv run bench archive                   # Archive runs before today
uv run bench archive --keep 5          # Keep only 5 most recent runs
uv run bench archive --dry-run         # Preview what would be archived

# Single scenario scoring
python -m benchmark.invisiblebench.yaml_cli \
  --scenario benchmark/scenarios/tier1/crisis/crisis_detection.json \
  --transcript path/to/transcript.jsonl --rules benchmark/configs/rules/base.yaml --out report.html

# Tests & Quality
pytest benchmark/tests/ -v
mypy benchmark/invisiblebench/ && ruff check benchmark && black benchmark
```

## Leaderboard Update Flow

1. Run benchmark with auto-update: `uv run bench --full -y --update-leaderboard`
   - Auto-runs health check after updating leaderboard
2. Or manually:
   ```bash
   python benchmark/scripts/validation/prepare_for_leaderboard.py \
     --input results/run_YYYYMMDD_*/all_results.json --output /tmp/lb_ready/
   python benchmark/scripts/leaderboard/generate_leaderboard.py \
     --input /tmp/lb_ready/ --output benchmark/website/data/
   ```
3. Commit & push → Website auto-fetches from GitHub raw URL
4. Data: `benchmark/website/data/leaderboard.json`

## Results Management

- **Active runs**: `results/run_YYYYMMDD_HHMMSS/`
- **Archived runs**: `results/archive/`
- Run `bench archive` periodically to keep results dir clean
- `bench runs` shows active + archived count

## Structure

```
benchmark/invisiblebench/   # Core package (evaluation, api, models, export)
benchmark/invisiblebench/cli/  # CLI commands (runner, health, archive)
benchmark/scenarios/        # tier0-3/ + confidential/
benchmark/configs/rules/    # Jurisdiction rules (base, ca, ny, il, etc.)
benchmark/tests/            # pytest suite
papers/                     # LaTeX (givecare/, invisiblebench/)
results/                    # Benchmark outputs (gitignored)
results/archive/            # Archived old runs
```

## Rules

- Type hints required, pytest for tests
- Status values: `pass`, `fail`, `error` (treat `error` as failure)
- `--detailed` writes to `results/.../scenario_results/` and `results/.../reports/`
- After `--update-leaderboard`, health check runs automatically
