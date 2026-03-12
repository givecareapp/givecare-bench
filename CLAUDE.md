# CLAUDE.md

Research benchmark project. Say "done" when finished (no verbose summaries).

## CLI

```bash
# Benchmark (primary: uv run bench) - tests raw LLMs
uv run bench --full -y                 # All configured models
uv run bench -m deepseek -y            # Single model by name
uv run bench -m gpt-5.2,claude -y      # Multiple models by name
uv run bench -m 1-4 -y                 # Models 1-4 (backward compat)
uv run bench -m 4 -c safety -y         # Model 4, safety category only
uv run bench -m 1-4 -p 4 -y            # 4 parallel
uv run bench -m deepseek --runs 3 -y   # 3 runs per scenario (median score)
uv run bench --dry-run                 # Cost estimate + current model catalog
uv run bench -m deepseek -y --detailed # Per-scenario JSON/HTML

# Rerun specific model (use after errors)
uv run bench -m gpt-5.2 -y --update-leaderboard   # Rerun GPT-5.2

# -m accepts names (partial, case-insensitive) or numbers.
# Use `uv run bench --dry-run` to see the current numbered catalog.

# GiveCare Eval Harness - tests Mira product (not raw LLM)
uv run bench --harness givecare --mode live -y         # Standard live/system path (44 scenarios)
uv run bench --provider givecare -y                    # Backward-compatible alias for live mode
uv run bench --harness givecare --mode orchestrator -y # Direct Pi orchestrator benchmark harness
uv run bench --harness givecare --mode orchestrator -m gemini-3.1-flash-lite-preview -y
uv run bench --harness givecare --mode live -y --confidential
uv run bench --harness givecare --mode live -c safety -y
uv run bench --harness givecare --mode live -y --diagnose
uv run bench --harness givecare --mode live -y --output results/givecare/run_name

# Run Audit + Diagnostic Reports
uv run bench audit results/run_YYYYMMDD_HHMMSS/                            # Benchmark run failure-mode audit
uv run bench audit results/givecare/run_YYYYMMDD_HHMMSS/                   # GiveCare live run audit
uv run bench audit results/givecare_orchestrator/run_YYYYMMDD_HHMMSS/      # GiveCare orchestrator run audit
uv run bench diagnose results/givecare/run_YYYYMMDD_HHMMSS/givecare_results.json      # From givecare live results
uv run bench diagnose results/givecare_orchestrator/run_YYYYMMDD_HHMMSS/all_results.json  # From orchestrator runs
uv run bench diagnose results/run_*/all_results.json                       # From raw model eval
uv run bench diagnose results.json -p previous.json                        # With comparison

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
| Raw LLM Eval | `uv run bench --full -y` | Base model capability with the benchmark prompt only | 44 |
| GiveCare Live Harness | `uv run bench --harness givecare --mode live -y` | Full Mira product path, including transport/runtime noise | 44 (or 47 with `--confidential`) |
| GiveCare Orchestrator Harness | `uv run bench --harness givecare --mode orchestrator -y` | Direct `@givecare/pi-orchestrator` policy/runtime behavior | 44 (or 47 with `--confidential`) |

**Scores are not directly comparable across these modes.** Raw eval measures base model capability. GiveCare live adds real product-path behavior. GiveCare orchestrator isolates the orchestrator with a benchmark-owned runtime shim, so it is cleaner than live mode but still not the same target as raw eval.

## Leaderboard Management

```bash
# Add model results to leaderboard (merges, doesn't overwrite)
uv run bench leaderboard add results/run_YYYYMMDD_HHMMSS/

# Rebuild from canonical files (results/leaderboard_ready/)
uv run bench leaderboard rebuild

# Health check
uv run bench leaderboard status       # or: uv run bench health

# Auto-update after benchmark run
uv run bench -m opus-4.6 -y --update-leaderboard
```

- Canonical per-model files: `results/leaderboard_ready/`
- Generated data: `data/v2/leaderboard.json`
- Commit & push → Website auto-fetches from GitHub raw URL
- Health check uses most-common scenario count as baseline (mixed counts OK)
- Leaderboard add / publish / `--update-leaderboard` are blocked when `run_audit.json` marks a run non-publishable

## Results Management

- **Active model runs**: `results/run_YYYYMMDD_HHMMSS/`
- **Active GiveCare live runs**: `results/givecare/run_YYYYMMDD_HHMMSS/`
- **Active GiveCare orchestrator runs**: `results/givecare_orchestrator/run_YYYYMMDD_HHMMSS/`
- **Primary scored artifacts**: `results/.../model_results/*.json` (one JSON per model/provider)
- **Compatibility aggregate**: `results/.../all_results.json`
- **Archived runs**: `results/archive/`
- Run `bench archive` periodically to keep results dir clean
- `bench runs` shows active + archived count

## Structure

```
benchmark/invisiblebench/       # Core package
  api/                          # API client (OpenRouter/OpenAI)
  cli/                          # CLI commands (runner, leaderboard, health, stats)
  evaluation/                   # Orchestrator + scorers (safety, compliance, regard, coordination, memory)
  export/                       # HTML/JSON report generation
  models/                       # Model config + pricing
  stats/                        # Statistical analysis (CIs, reliability, annotation)
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
benchmark/adapters/             # Non-Python target adapters owned by the benchmark
  givecare-orchestrator/        # TS bridge bundle for direct Pi orchestrator evals
benchmark/scripts/              # Provider implementations + validation
benchmark/tests/                # pytest suite
autoresearch/                   # Autonomous scenario optimization (see autoresearch/CLAUDE.md)
data/v2/                        # Published leaderboard (committed, fetched by web app)
docs/                           # MkDocs site + scoring rubric
papers/                         # LaTeX (givecare/, invisiblebench/)
scripts/                        # Repo-level scripts (post_discussion.sh)
results/                        # Outputs (gitignored)
  leaderboard_ready/            # Canonical per-model score files
  run_YYYYMMDD_HHMMSS/          # Raw LLM benchmark run
    model_results/              # One JSON per model
  givecare/run_YYYYMMDD_HHMMSS/ # GiveCare live eval run
    model_results/              # One JSON per provider target
  givecare_orchestrator/run_YYYYMMDD_HHMMSS/  # Direct orchestrator harness run
    model_results/              # One JSON per orchestration model
  autoresearch/                 # Autoresearch probe runs
  archive/                      # Old runs
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
- **All implemented transcript generators**: Works in raw model eval, GiveCare live mode, and GiveCare orchestrator mode
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
