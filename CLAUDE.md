# CLAUDE.md

AI assistant instructions for givecare-bench (research benchmark project).

## ⚠️ CRITICAL RULES

- **No unnecessary documentation**: Ask before creating new .md files
- When done: Say "done" (no verbose summaries)
- Keep the repo minimal and focused

## Project Type

**Research project in active development** (not production maintenance).
- Writing papers (LaTeX in `papers/`)
- Developing benchmark (Python in `benchmark/`)
- Running experiments (`dev/experiments/`)

## Repo Split

| Repo | Location | Responsibility |
|------|----------|----------------|
| **givecare-bench** | `~/Projects/give-care-else/givecare-bench` | Benchmark code, scenarios, papers, experiments |
| **givecare** (monorepo) | `~/Projects/givecare` | Production app, **live website** |

## Update Ripple Flow

When benchmark results change, updates flow through this pipeline:

```
1. Run benchmark
   python -m benchmark.invisiblebench.cli --scenarios benchmark/scenarios/tier0

2. Results saved to results/run_YYYYMMDD_*/

3. Update leaderboard.json (in this repo)
   benchmark/website/data/leaderboard.json

4. Push to givecare-bench (triggers GitHub raw URL update)
   git add benchmark/website/data/leaderboard.json
   git commit -m "Update leaderboard with new results"
   git push

5. Website auto-fetches from GitHub raw URL:
   https://raw.githubusercontent.com/givecareapp/givecare-bench/main/benchmark/website/data/leaderboard.json

   (Fallback: copy to givecare repo manually if GitHub fetch fails)
```

**Data format:**
- `overall_leaderboard` — Full benchmark (tier1-3), matches paper v1
- `tier0_leaderboard` — Smoke tests (5 scenarios), quick validation
- Scenario `status` values: `pass`, `fail`, `error` (treat `error` as failure)
- `--detailed` runs write per-scenario JSON/HTML to `results/.../scenario_results` and `results/.../reports`

**Website components:**
- `LeaderboardTable` — Renders overall_leaderboard
- `Tier0Table` — Renders tier0_leaderboard
- `useLeaderboardData` — Fetches from GitHub raw URL, falls back to local

## Automated Systems

**Skills auto-activate** based on keywords/files:
- "research" → research-methodology skill
- "paper"/"figure" → paper-code-alignment skill
- "design"/"should we" → design-iteration skill
- "experiment"/"validate" → experimental-validation skill

**Hooks auto-run** after you finish:
- Python edits → pytest, mypy, ruff
- LaTeX edits → Paper-code alignment reminders

## CLI Commands

```bash
# === BENCHMARKING (primary CLI: uv run bench) ===
# Quick validation (1 model × all scenarios, ~$0.05)
uv run bench --minimal -y

# Full benchmark (10 models × all scenarios, ~$5-10)
uv run bench --full -y

# Model selection (1-indexed):
#   1=Opus 4.5, 2=GPT-5.2, 3=Gemini 3 Pro, 4=Sonnet 4.5,
#   5=Grok 4, 6=GPT-5 Mini, 7=DeepSeek V3.2, 8=Gemini 2.5 Flash,
#   9=MiniMax M2.1, 10=Qwen3 235B
uv run bench --full -m 1-4 -y          # First 4 models
uv run bench --full -m 4 -t 3 -y       # Model 4 (Sonnet), tier 3 only
uv run bench --full -m 1,3,5 -y        # Specific models
uv run bench --full -m 4- -y           # Models 4 onwards

# Tier selection
uv run bench --full -t 0,1 -y          # Tier 0 and 1 only
uv run bench --full -t 3 -y            # Tier 3 only

# Parallel execution
uv run bench --full -m 1-4 -p 4 -y     # 4 models in parallel

# Detailed per-scenario JSON/HTML (turn flags)
uv run bench --minimal -y --detailed

# Dry run (estimate cost only)
uv run bench --dry-run

# === SCORING (single scenario) ===
python -m benchmark.invisiblebench.yaml_cli \
  --scenario benchmark/scenarios/tier1/crisis/crisis_detection.json \
  --transcript path/to/transcript.jsonl \
  --rules benchmark/configs/rules/base.yaml \
  --out report.html

# === LEADERBOARD ===
python benchmark/scripts/validation/prepare_for_leaderboard.py \
  --results results/run_*/all_results.json \
  --output benchmark/website/data/leaderboard.json

# === VALIDATION/LINTING ===
python benchmark/scripts/validation/check_ready.py          # Pre-run checks
python benchmark/scripts/validation/lint_turn_indices.py    # Validate scenario structure
python benchmark/scripts/validation/lint_doc_commands.py    # Validate doc commands

# === TESTS ===
pytest benchmark/tests/ -v                                  # All tests
pytest benchmark/tests/ -v --cov=benchmark.invisiblebench   # With coverage

# === CODE QUALITY ===
mypy benchmark/invisiblebench/    # Type check
ruff check benchmark              # Lint
black benchmark                   # Format

# === PAPERS ===
cd papers/givecare && pdflatex GiveCare.tex && bibtex GiveCare && pdflatex GiveCare.tex
python papers/givecare/generate_figures.py
```

## Code Style

**Python:**
- Type hints required
- Docstrings for public methods
- pytest for tests (in `benchmark/tests/`)

**LaTeX:**
- Cite as: `\cite{author2025key}`
- Figures: `\includegraphics[width=0.8\textwidth]{fig.pdf}`
- **IMPORTANT**: Use correct WOPR Act citation (Illinois HB1806/PA 104-0054)

## Dev Docs Workflow (For 3+ Day Features)

1. Plan in planning mode FIRST
2. `/create-dev-docs [task-name]` → Creates `dev/active/[task-name]/`
3. Update tasks as you complete them
4. Before context low: `/update-dev-docs`
5. New session: Say "continue"

## Repository Structure

```
benchmark/              # Core benchmark package
  invisiblebench/       # Python package (32 files)
    evaluation/         # Scoring orchestrator & scorers
    api/               # Model API client
    loaders/           # YAML/JSON loaders
    models/            # Data models
    export/            # Report generators
    cli.py             # BenchmarkRunner
    yaml_cli.py        # Main CLI tool
  scenarios/           # 25 test scenarios (JSON)
    tier0/             # 5 smoke tests
    tier1/             # 5 scenarios (3-5 turns)
    tier2/             # 9 scenarios (8-12 turns)
    tier3/             # 3 scenarios (20+ turns)
    confidential/      # 3 adversarial tests
  configs/             # Configuration files
    rules/             # 7 jurisdiction rules
    scoring.yaml       # Dimension weights
  scripts/             # Execution scripts
    validation/        # Runner scripts
    cloud/             # Modal deployment
    community/         # Leaderboard tools
  tests/               # Test suite (90 tests)
  docs/                # Documentation
  examples/            # 1 example
  website/             # Leaderboard HTML
  huggingface/         # HF dataset tools

papers/                # LaTeX papers
  givecare/            # GiveCare system paper
  invisiblebench/      # InvisibleBench benchmark paper

dev/                   # Development artifacts
  active/              # Current work
  experiments/         # Research experiments
  completed/           # Archived tasks
  archive/             # Old work

docs/                  # Research reference docs (not committed)
```

## Repository Philosophy

**Keep it minimal:**
- No research/analysis scripts in production code
- No orphaned files or duplicates
- No system cruft (.DS_Store, __pycache__)
- Archive completed work to `dev/archive/`
- Reference materials in `docs/` (not committed)

## Repository Etiquette

- Commit messages: Descriptive (not "fix bug")
- Paper changes: Include figure regeneration if needed
- Test changes: Run full suite before committing
- Before cleanup: Verify files aren't referenced in code

## See Also

- `ARXIV_REFERENCE.md` - ArXiv submission guide
- `.claude/skills/` - Detailed research methodology guidance (auto-activates)
- `dev/experiments/` - Research notes and pre-registered experiments
