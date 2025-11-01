# CLAUDE.md

AI assistant instructions for givecare-bench (research benchmark project).

## ⚠️ CRITICAL RULES

**MAXIMUM 15 .md FILES IN REPO. NO EXCEPTIONS.**
- Before creating ANY .md: Ask user approval
- When done: Say "done" (no summary documents)

## Project Type

**Research project in design/test phase** (not production maintenance).
- Writing papers (LaTeX in `papers/`)
- Developing benchmark (Python in `benchmark/`)
- Running experiments (`dev/experiments/`)

## Automated Systems (You Don't Need to Ask)

**Skills auto-activate** based on keywords/files:
- "research" → research-methodology skill
- "paper"/"figure" → paper-code-alignment skill
- "design"/"should we" → design-iteration skill
- "experiment"/"validate" → experimental-validation skill

**Hooks auto-run** after you finish:
- Python edits → pytest, mypy, ruff
- LaTeX edits → Paper-code alignment reminders

## Bash Commands

```bash
# Tests
pytest benchmark/tests/ -v

# Run evaluation
python benchmark/scripts/validation/run_minimal.py

# LaTeX compile
cd papers/givecare && pdflatex GiveCare.tex && bibtex GiveCare && pdflatex GiveCare.tex

# Generate figures
python papers/givecare/generate_figures.py

# Type check
mypy benchmark/supportbench/
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
benchmark/
  supportbench/     # Python package - scoring logic
  scenarios/        # Test scenarios
  tests/            # Test suite
  scripts/          # Validation scripts
papers/
  givecare/         # GiveCare system paper (LaTeX)
  supportbench/     # SupportBench benchmark paper (LaTeX)
dev/
  active/           # Current work in progress
  experiments/      # Research experiments
  completed/        # Archived tasks
```

## Repository Etiquette

- Commit messages: Descriptive (not "fix bug")
- Paper changes: Include figure regeneration if needed
- Test changes: Run full suite before committing

## See Also

- `ARXIV_REFERENCE.md` - ArXiv submission guide
- `.claude/skills/` - Detailed research methodology guidance (auto-activates)
- `dev/experiments/` - Research notes and pre-registered experiments
