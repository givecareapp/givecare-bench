# CLAUDE.md

Research benchmark project. Say "done" when finished (no verbose summaries).

## CLI

```bash
# Benchmark (primary: uv run bench) - tests raw LLMs
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

# GiveCare Provider - tests Mira product (not raw LLM)
uv run bench --provider givecare -y                    # Standard (29 scenarios)
uv run bench --provider givecare -y --confidential     # Full (32 scenarios)
uv run bench --provider givecare -t 1 -y               # Tier 1 only
uv run bench --provider givecare -y --diagnose         # With diagnostic report

# Diagnostic Reports (actionable fix suggestions)
uv run bench diagnose results/givecare/givecare_results.json   # From givecare results
uv run bench diagnose results/run_*/all_results.json           # From model eval
uv run bench diagnose results.json -p previous.json            # With comparison

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

## Benchmark vs Product Eval

| Mode | Command | What it tests | Scenarios |
|------|---------|---------------|-----------|
| Model Eval | `uv run bench --full -y` | Raw LLM capability | 29 |
| System Eval | `uv run bench --provider givecare -y` | Mira product behavior | 29 (or 32 with --confidential) |

**Scores are NOT directly comparable** - model eval tests raw models with simple prompt, system eval tests full product stack (tools, memory, SMS constraints).

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
benchmark/invisiblebench/       # Core package (evaluation, api, models, export)
benchmark/invisiblebench/cli/   # CLI commands (runner with --provider flag)
benchmark/scripts/              # Provider implementations
  givecare_provider.py          # GiveCare/Mira system provider
benchmark/scenarios/            # tier0-3/ (29) + confidential/ (3)
benchmark/configs/rules/        # Jurisdiction rules (base, ca, ny, il, etc.)
benchmark/tests/                # pytest suite
papers/                         # LaTeX (givecare/, invisiblebench/)
results/                        # Outputs (gitignored)
  run_YYYYMMDD_HHMMSS/          # Model eval runs (--provider openrouter)
  givecare/                     # System eval runs (--provider givecare)
    transcripts/                # Conversation transcripts
    givecare_results.json       # Scored results
  archive/                      # Archived old runs
```

## Diagnostic Reports

`--diagnose` generates actionable markdown reports with:

- **Failure priority** - hard fails first, then by score
- **Quoted responses** - actual user/assistant messages from transcripts
- **Violation details** - turn number, rule violated, dimension
- **Suggested fixes** - specific prompt/code changes to investigate
- **Pattern analysis** - common issues across scenarios
- **Comparison** - diff from previous run (if `-p` provided)

Output: `diagnostic_report.md` in results directory

## Conditional Branching

Scenarios can include conditional branches where the user's next message depends on the model's response. This is automatic — no CLI flags needed.

- **How it works**: After each model response, `resolve_branch()` checks the next turn for branch conditions. If a condition matches, an alternate user message is sent instead of the default.
- **5 branched scenarios**: medical_boundary_violation (T3), venting_vs_crisis (T2), crisis_recovery_test (T2), attachment_formation (T7), longitudinal_trust (T9)
- **Condition types**: `contains_any`, `contains_all`, `not_contains`, `regex`
- **Both eval modes**: Works in model eval (runner.py) and system eval (givecare_provider.py)
- **Transcript audit**: Branch IDs recorded in JSONL (`"branch_id": "boundary_failed"`)
- **Rerun required**: Branching changes transcript content for these 5 scenarios

## Scorer Cache

LRU cache for temperature=0 scorer LLM calls (belonging, safety, trauma):
- **Default**: 256 entries, enabled automatically for temp=0 calls with `use_cache=True`
- **Configure**: `INVISIBLEBENCH_SCORER_CACHE_SIZE=512` (set to 0 to disable)
- **How it works**: SHA256 hash of normalized payload → cached response (deepcopy on read)
- **Impact**: ~40% API cost reduction on repeated evaluations

## Rules

- Type hints required, pytest for tests
- Status values: `pass`, `fail`, `error` (treat `error` as failure)
- `--detailed` writes to `results/.../scenario_results/` and `results/.../reports/`
- `--diagnose` writes `diagnostic_report.md` with actionable fixes
- After `--update-leaderboard`, health check runs automatically
