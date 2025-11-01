# Paper-Code Alignment Skill

## When to Use
Writing papers, implementing features described in papers, generating figures, reviewing claims

## The Alignment Problem

Papers make claims. Code must support those claims. Misalignment = non-reproducible research.

### Bidirectional Checks

#### From Paper → Code
When writing a paper claim:
- [ ] Does the code actually implement this?
- [ ] Can we reproduce the figure from the implementation?
- [ ] Are the numbers in the paper from actual runs?
- [ ] Is the algorithm description accurate?

#### From Code → Paper
When implementing a feature:
- [ ] Is this design decision documented in the paper?
- [ ] Should this be mentioned in methodology?
- [ ] Does this affect any claims or results?
- [ ] Do we need a new figure to explain this?

## Project Structure

```
papers/givecare/GiveCare.tex         ← Claims about GiveCare system
papers/supportbench/SupportBench.tex  ← Claims about benchmark methodology
benchmark/supportbench/              ← Must match paper descriptions
benchmark/scenarios/                 ← Scenarios must match paper counts/descriptions
```

## Figure Generation Workflow

### Standard Process

1. **Implement feature/experiment** in `benchmark/`
2. **Run evaluation**:
   ```bash
   # Minimal validation
   python benchmark/scripts/validation/run_minimal.py

   # Full evaluation
   python -m supportbench.yaml_cli \
     --scenario benchmark/scenarios/tier1/crisis/crisis_detection.json \
     --transcript output/transcript.jsonl \
     --out results.html
   ```
3. **Generate figure**:
   ```bash
   python papers/givecare/generate_figures.py
   python papers/supportbench/figures/generate_hero_figure.py
   ```
4. **Verify figure matches paper claim**
5. **Update LaTeX**:
   ```latex
   \begin{figure}[ht]
   \centering
   \includegraphics[width=0.8\textwidth]{fig1_hero_flow.pdf}
   \caption{System architecture showing...}
   \label{fig:hero}
   \end{figure}
   ```

### Existing Figure Generation Scripts

Your project has:
- `papers/givecare/generate_figures.py` - Main figure generation
- `papers/givecare/generate_hero_figure.py` - Hero/flow diagrams
- `papers/supportbench/figures/generate_hero_figure.py` - Benchmark diagrams

When creating figures:
- Output to `papers/*/figures/*.pdf` or `papers/*/*.pdf`
- Use PDF format (vector graphics, scales cleanly)
- Include descriptive filenames: `fig1_hero_flow.pdf`, `fig6_multiagent_architecture.pdf`

## Version Synchronization

Track in CLAUDE.md or dev/sync-status.md:

```markdown
## Paper-Code Sync Status

**GiveCare Paper (v0.8.5)**:
- Section 3.2 (Multi-Agent Architecture): ✅ Matches `supportbench/scorers/`
- Section 4.1 (Evaluation Metrics): ⚠️  Paper shows 8 dimensions, code has 7
- Figure 6: ✅ Generated from `generate_hero_figure.py`
- Table 3 (Weights): ✅ Matches `configs/scoring.yaml`

**SupportBench Paper (v0.8.5)**:
- Section 2.1 (Tier Structure): ✅ Matches `benchmark/scenarios/tier*/`
- Section 3.3 (Scoring): ✅ Matches dimension weights in code
- Figure 1: ⚠️  Needs regeneration after recent changes

**Last Sync Check**: 2025-10-30
```

## Red Flags to Catch

### Common Misalignments

- ❌ Paper says "we use X algorithm" but code uses Y
- ❌ Paper reports N=100 scenarios, code has 17 scenarios
- ❌ Figure shows different architecture than implementation
- ❌ Paper claims "statistically significant" but no stats in code
- ❌ Table shows dimension weight = 15%, code has 10%
- ❌ Paper describes 8 dimensions, code implements 7
- ❌ Figure generated before recent refactor

### Validation Checklist

Before paper submission:
- [ ] Run all figure generation scripts to ensure they work
- [ ] Verify all numbers in tables come from actual runs (not placeholders)
- [ ] Check scenario counts match between paper and `benchmark/scenarios/`
- [ ] Validate dimension weights match between LaTeX and `configs/scoring.yaml`
- [ ] Ensure all algorithm descriptions match implementation
- [ ] Verify all cited files/paths exist in the repo

## LaTeX Integration

### Referencing Code in Papers

When describing implementation:

```latex
\subsection{Scoring Implementation}

Our benchmark implements 8 evaluation dimensions (Section~\ref{sec:dimensions})
with weights optimized through empirical calibration. The scoring orchestrator
(see \texttt{benchmark/supportbench/orchestrator.py}) coordinates independent
scorers for each dimension...
```

### Maintaining Consistency

Key locations to keep in sync:

| Paper Location | Code Location | Check |
|----------------|---------------|-------|
| Table 1: Dimension Weights | `configs/scoring.yaml` | Weights match? |
| Section 2: Tier Structure | `benchmark/scenarios/tier*/` | Turn counts match? |
| Figure 3: Architecture | `supportbench/scorers/` | Components match? |
| Table 4: Scenario Counts | `benchmark/scenarios/` | N matches? |
| Section 4: Autofails | `orchestrator.py` hard_fail logic | Conditions match? |

### arXiv Submission Checklist

From your `ARXIV_SUBMISSION_READY.md`:
- [ ] All figures in PDF/PNG format (no JPEG for line art)
- [ ] Correct WOPR Act citation: Illinois HB1806 / PA 104-0054
- [ ] References.bib has all papers cited in design decisions
- [ ] All \cite{} commands have matching BibTeX entries
- [ ] Figure generation scripts documented and runnable
- [ ] README explains how to reproduce figures

## Integration with This Project

### Current Paper Status (from git status)

```
M papers/givecare/GiveCare.tex
M papers/givecare/manuscript.md
M papers/givecare/references.bib
M papers/supportbench/SupportBench.tex
M papers/supportbench/references.bib
```

You have active edits in both papers. Before committing:
1. Run figure generation scripts
2. Verify all figures are up-to-date
3. Check dimension weights in both papers match code
4. Validate scenario counts

### Figure Files Present

Your project has these generated figures in `papers/givecare/`:
- `fig1_hero_flow.pdf`
- `fig6_multiagent_architecture.pdf`
- `fig7_gcsdoh_domains.pdf`
- `fig8_burnout_scoring.pdf`
- `fig9_beta_results.pdf`
- `fig10_dspy_optimization.pdf`
- `fig11_pressure_zones.pdf`
- `fig12_longitudinal_trajectory.pdf`
- `fig13_confusion_matrix.pdf`
- `fig14_gcsdoh_instrument.pdf`
- `fig15_comparison_table.pdf`
- `fig16_metrics_dashboard.pdf`

When editing papers, verify:
1. All \includegraphics{} commands point to existing files
2. Figure captions accurately describe what's shown
3. Figures were generated from current code (not stale)

### When to Regenerate Figures

Regenerate when:
- Architecture changes (update fig6_multiagent_architecture.pdf)
- Dimension weights change (update fig8_burnout_scoring.pdf)
- New experimental results (update fig9_beta_results.pdf, fig13_confusion_matrix.pdf)
- Scenario structure changes (update fig1_hero_flow.pdf)

## Workflow Integration

### During Feature Development

```markdown
1. Plan feature (with research grounding)
2. Implement in benchmark/
3. Run tests: pytest benchmark/tests/ -v
4. Run evaluation to get data
5. Generate figures: python papers/*/generate_figures.py
6. Update paper LaTeX with new results
7. Verify figure matches claim
8. Commit code + figures + paper updates together
```

### Before Paper Submission

```bash
# Regenerate all figures
python papers/givecare/generate_figures.py
python papers/givecare/generate_hero_figure.py
python papers/supportbench/figures/generate_hero_figure.py

# Verify LaTeX compiles
cd papers/givecare && pdflatex GiveCare.tex && bibtex GiveCare && pdflatex GiveCare.tex
cd papers/supportbench && pdflatex SupportBench.tex && bibtex SupportBench && pdflatex SupportBench.tex

# Check alignment
# Read both .tex files and verify claims match code
```

## See Also
- [Resource: Reproducibility Checklist](resources/reproducibility-checklist.md)
- [Resource: Figure Generation Guide](resources/figure-generation-guide.md)
