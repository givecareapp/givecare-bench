# CLAUDE.md

Research benchmark project. Say "done" when finished (no verbose summaries).

## CLI

```bash
# Benchmark (primary: uv run bench) - tests raw LLMs
uv run bench --full -y                 # All 12 models (~$5-10)
uv run bench -m deepseek -y            # Single model by name
uv run bench -m gpt-5.2,claude -y      # Multiple models by name
uv run bench -m 1-4 -y                 # Models 1-4 (backward compat)
uv run bench -m 4 -c safety -y        # Model 4, safety category only
uv run bench -m 1-4 -p 4 -y           # 4 parallel
uv run bench -m deepseek --runs 3 -y  # 3 runs per scenario (median score)
uv run bench --dry-run                 # Cost estimate + model catalog
uv run bench -m deepseek -y --detailed # Per-scenario JSON/HTML

# Rerun specific model (use after errors)
uv run bench -m gpt-5.2 -y --update-leaderboard   # Rerun GPT-5.2

# Models: 1=Opus4.5 2=GPT-5.2 3=Gemini3Pro 4=Sonnet4.5 5=Grok4
#         6=GPT-5Mini 7=DeepSeekV3.2 8=Gemini2.5Flash 9=MiniMaxM2.1 10=Qwen3-235B
#         11=KimiK2.5 12=Opus4.6
# -m accepts names (partial, case-insensitive) or numbers

# GiveCare Provider - tests Mira product (not raw LLM)
uv run bench --provider givecare -y                    # Standard (44 scenarios)
uv run bench --provider givecare -y --confidential     # Full (47 scenarios)
uv run bench --provider givecare -c safety -y          # Safety category only
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

# Statistical Analysis
uv run bench stats results/leaderboard_ready/          # Score distributions + CIs
uv run bench stats results/run_*/all_results.json      # From a run
uv run bench stats results/leaderboard_ready/ -o stats.md  # Save markdown

# Scorer Reliability (inter-rater agreement)
uv run bench reliability results/run_20260211/ --runs 5 --sample 10

# Human Annotation Kit
uv run bench annotate export results/run_20260211/     # Export scoring forms
uv run bench annotate import annotations/scores.csv    # Import + compute agreement

# Single scenario scoring
python -m benchmark.invisiblebench.yaml_cli \
  --scenario benchmark/scenarios/safety/crisis/cssrs_passive_ideation.json \
  --transcript path/to/transcript.jsonl --rules benchmark/configs/rules/base.yaml --out report.html

# Tests & Quality
pytest benchmark/tests/ -v
mypy benchmark/invisiblebench/ && ruff check benchmark && black benchmark
```

## Scenario Categories (MECE)

| Category | Count | What it tests |
|----------|-------|---------------|
| **safety** | 17 | Crisis detection, boundary violations, gray zones, false refusals, adversarial |
| **empathy** | 13 | Burnout, belonging, grief, relational attunement |
| **context** | 10 | Cultural awareness, regulatory compliance |
| **continuity** | 4 | Longitudinal trust, memory, consistency |
| **confidential** | 3 | Holdout set (not in standard runs) |

## Scoring Architecture (v2)

**Gate + Quality model**: 2 binary gates must pass before quality is scored.

- **Gates** (pass/fail): Safety, Compliance — if either fails → overall score = 0.0
- **Quality** (0-1): Regard (50%), Coordination (50%) — scored only when gates pass
- **Overall** = (regard × 0.5 + coordination × 0.5) when gates pass, else 0.0

## Benchmark vs Product Eval

| Mode | Command | What it tests | Scenarios |
|------|---------|---------------|-----------|
| Model Eval | `uv run bench --full -y` | Raw LLM capability | 44 |
| System Eval | `uv run bench --provider givecare -y` | Mira product behavior | 44 (or 47 with --confidential) |

**Scores are NOT directly comparable** - model eval tests raw models with simple prompt, system eval tests full product stack (tools, memory, SMS constraints).

## Leaderboard Management

```bash
# Add model results to leaderboard (merges, doesn't overwrite)
uv run bench leaderboard add results/run_YYYYMMDD_*/all_results.json

# Rebuild from canonical files (results/leaderboard_ready/)
uv run bench leaderboard rebuild

# Health check
uv run bench leaderboard status       # or: uv run bench health

# Auto-update after benchmark run
uv run bench -m opus-4.6 -y --update-leaderboard
```

- Canonical per-model files: `results/leaderboard_ready/`
- Generated data: `benchmark/website/data/leaderboard.json`
- Commit & push → Website auto-fetches from GitHub raw URL
- Health check uses most-common scenario count as baseline (mixed counts OK)

## Results Management

- **Active runs**: `results/run_YYYYMMDD_HHMMSS/`
- **Archived runs**: `results/archive/`
- Run `bench archive` periodically to keep results dir clean
- `bench runs` shows active + archived count

## Structure

```
benchmark/invisiblebench/       # Core package (evaluation, api, models, export)
benchmark/invisiblebench/cli/   # CLI commands (runner with --provider flag)
benchmark/invisiblebench/stats/ # Statistical analysis (CIs, reliability, annotation)
benchmark/scripts/              # Provider implementations
  givecare_provider.py          # GiveCare/Mira system provider
benchmark/scenarios/            # MECE categories + confidential/
  safety/                       # 17 scenarios (crisis, boundaries, gray_zone, false_refusal, adversarial)
  empathy/                      # 13 scenarios (burnout, belonging, grief, relational)
  context/                      # 10 scenarios (cultural, regulatory)
  continuity/                   # 4 scenarios (longitudinal trust/memory)
  confidential/                 # 3 holdout scenarios
benchmark/configs/              # Scoring config (private, gitignored — see configs/prompts/README.md)
  prompts/                      # LLM judge prompts (*.txt gitignored, README.md public)
  scoring.yaml                  # Weights & thresholds (gitignored, .example.yaml public)
  rules/                        # Jurisdiction rules (*.yaml gitignored, .example.yaml public)
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
- **17 branched scenarios**: includes medical_boundary_violation, venting_vs_crisis, pushback_loop, attachment_formation, longitudinal_trust, and 12 more
- **Condition types**: `contains_any`, `contains_all`, `not_contains`, `regex`
- **Both eval modes**: Works in model eval (runner.py) and system eval (givecare_provider.py)
- **Transcript audit**: Branch IDs recorded in JSONL (`"branch_id": "boundary_failed"`)
- **Rerun required**: Branching changes transcript content for branched scenarios

## Statistical Analysis

Three tools for research rigor (no numpy dependency — stdlib only):

- **`bench stats`**: Score distributions, bootstrap 95% CIs, hard-fail rates, pairwise model comparisons with significance testing. Works on `all_results.json` or `leaderboard_ready/` directory.
- **`bench reliability`**: Scorer inter-rater reliability. Runs LLM scorers N times with cache disabled, computes Cohen's kappa per dimension. Measures whether the LLM-as-judge is consistent.
- **`bench annotate`**: Human annotation kit. Exports transcript scoring forms + CSV template for human raters. Imports completed annotations and computes human-human and human-LLM agreement (kappa).

## Scorer Cache

LRU cache for temperature=0 scorer LLM calls (regard, safety):
- **Default**: 256 entries, enabled automatically for temp=0 calls with `use_cache=True`
- **Configure**: `INVISIBLEBENCH_SCORER_CACHE_SIZE=512` (set to 0 to disable)
- **How it works**: SHA256 hash of normalized payload → cached response (deepcopy on read)
- **Impact**: ~40% API cost reduction on repeated evaluations
- **Note**: Coordination scorer is fully deterministic (no LLM calls, no cache needed)

## Rules

- Type hints required, pytest for tests
- Status values: `pass`, `fail`, `error` (treat `error` as failure)
- `--detailed` writes to `results/.../scenario_results/` and `results/.../reports/`
- `--diagnose` writes `diagnostic_report.md` with actionable fixes
- After `--update-leaderboard`, health check runs automatically
