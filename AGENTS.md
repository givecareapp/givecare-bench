# Repository Guidelines

## Project Structure & Module Organization
- Core code lives in `benchmark/invisiblebench/` (evaluation orchestrators, loaders, models, utils). Scenarios are in `benchmark/scenarios/` grouped by `tier1/`, `tier2/`, `tier3/`; scoring configs in `benchmark/configs/`; runnable helpers in `benchmark/scripts/`. Tests sit in `benchmark/tests/` with fixtures in `benchmark/tests/fixtures/`. Quick examples in `benchmark/examples/quick_start.py`. Research papers are under `papers/`; working notes and references sit in `docs/`. Generated artifacts (`results/`, `runs/`, coverage outputs) are git-ignored—keep them local.

## Build, Test, and Development Commands

**Setup:** Python ≥3.9. Recommended: `uv venv && source .venv/bin/activate && uv pip install -e ".[all]"`

**Benchmarking:**
```bash
python benchmark/scripts/validation/run_minimal.py -y      # Quick (22 scenarios, ~$0.05)
python benchmark/scripts/validation/run_full.py -y         # Full (~$30-40)
python benchmark/scripts/validation/run_minimal.py --dry-run  # Cost estimate only
```

**Single Scenario Scoring:**
```bash
python -m benchmark.invisiblebench.yaml_cli \
  --scenario benchmark/scenarios/tier1/crisis/crisis_detection.json \
  --transcript path/to/transcript.jsonl \
  --rules benchmark/configs/rules/base.yaml \
  --out report.html
```

**Leaderboard Update:**
```bash
python benchmark/scripts/validation/prepare_for_leaderboard.py \
  --results results/run_*/all_results.json \
  --output benchmark/website/data/leaderboard.json
```

**Validation/Linting:**
```bash
python benchmark/scripts/validation/check_ready.py          # Pre-run checks
python benchmark/scripts/validation/lint_turn_indices.py    # Validate scenarios
python benchmark/scripts/validation/lint_doc_commands.py    # Validate docs
```

**Tests:** `pytest benchmark/tests/ -v` (coverage: add `--cov=benchmark.invisiblebench`)

**Code Quality:** `mypy benchmark/invisiblebench/` | `ruff check benchmark` | `black benchmark`

## Coding Style & Naming Conventions
- Black-formatted Python with 100-character lines; run `black benchmark` before pushing. Ruff is enabled for linting (`ruff check benchmark`), following Pycodestyle/Pyflakes/Isort/Bugbear/Comprehensions; fixable issues should be auto-formatted (`ruff check --fix`). Mypy is configured but allows gradual typing—add type hints for new modules when feasible. Prefer snake_case modules/files; keep functions small and pure; document non-obvious logic with brief docstrings or comments.
- Tests follow `test_*.py` files, `Test*` classes, and `test_*` functions (see `pyproject.toml`), colocated near the code they exercise.

## Testing Guidelines
- Add focused tests in `benchmark/tests/unit/` for pure logic and `benchmark/tests/integration/` for end-to-end flows (scenario loading, scoring pipelines). Use fixtures under `benchmark/tests/fixtures/` for transcripts/rules instead of inlining JSON/YAML. For new scoring rules or scenarios, include at least one regression test proving expected scores or autofail behavior. Run `pytest -v` before raising a PR; include coverage flags when touching evaluators.

## Commit & Pull Request Guidelines
- Commit messages in this repo are short and descriptive (e.g., “Update papers with latest figures”); use imperative/present tense and group related changes. Avoid committing generated reports, large artifacts, or .env files.
- PRs should summarize scope, highlight scenario/rules changes, and link any issue or paper section they support. Include: (1) commands run with results (`pytest`, validation scripts), (2) sample output paths (e.g., `results/report.html`), and (3) notes on API/model requirements. Screenshots are only needed for website/visual changes.

## Security & Configuration Tips
- Keep API keys in `.env` (`OPENROUTER_API_KEY`); do not commit secrets. Use small test transcripts when developing to avoid unnecessary spend. When sharing logs, redact PHI/PII from scenarios or transcripts. Clean up cached results before publishing branches.***

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

