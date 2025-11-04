# Repository Structure - givecare-bench

**Clean and organized for arXiv/GitHub submission**

## Root Directory

```
givecare-bench/
├── CLAUDE.md                    # AI assistant instructions
├── README.md                    # Project overview
├── ARXIV_REFERENCE.md          # ArXiv submission guide
├── .gitignore                  # Git ignore patterns (NEW)
│
├── docs/                       # Documentation (NEW)
│   └── submission-guides/
│       ├── SUBMISSION_READY_SUMMARY.md      # Complete status report
│       └── FIGURE_REGENERATION_GUIDE.md     # Optional figure improvements
│
├── papers/                     # LaTeX papers
│   ├── supportbench/
│   │   ├── SupportBench.tex   # Main LaTeX source
│   │   ├── SupportBench.pdf   # Final PDF (26 pages, 640KB)
│   │   ├── references.bib     # Bibliography
│   │   ├── figures/           # Generated figures
│   │   └── scripts/           # Figure generation scripts
│   │
│   └── givecare/
│       ├── GiveCare.tex       # Main LaTeX source
│       ├── GiveCare.pdf       # Final PDF (41 pages, 1.2MB)
│       ├── references.bib     # Bibliography (inline)
│       ├── figures/           # Generated figures
│       ├── tables/            # LaTeX tables (includes table_gcsdoh28.tex)
│       └── scripts/           # Figure generation scripts
│
├── benchmark/                  # SupportBench evaluation code
│   ├── supportbench/          # Python package
│   ├── scenarios/             # Test scenarios (JSON)
│   ├── configs/               # Scoring configurations (YAML)
│   ├── tests/                 # Test suite
│   └── scripts/
│       └── validation/        # Evaluation scripts
│           ├── run_minimal.py
│           └── run_full.py
│
└── dev/                       # Development artifacts
    ├── active/                # Current work
    ├── completed/             # Archived tasks
    └── experiments/           # Research experiments
```

## Cleaned Files

**Removed temporary files:**
- ✓ LaTeX build artifacts (*.aux, *.log, *.out, *.bbl, *.blg, etc.)
- ✓ macOS system files (.DS_Store)
- ✓ Editor temporary files (*~, *.swp)

**Essential files preserved:**
- ✓ Final PDFs (SupportBench.pdf, GiveCare.pdf)
- ✓ LaTeX sources (*.tex, *.bib)
- ✓ Figures and tables
- ✓ Python evaluation code
- ✓ Documentation

## Key Documentation

### For Submission
- `docs/submission-guides/SUBMISSION_READY_SUMMARY.md` - Complete submission checklist
- `papers/supportbench/SupportBench.pdf` - Ready for NeurIPS D&B
- `papers/givecare/GiveCare.pdf` - Ready for CHI/IMWUT/JMIR

### For Optional Polish
- `docs/submission-guides/FIGURE_REGENERATION_GUIDE.md` - 1-hour figure improvements

### For Development
- `CLAUDE.md` - AI assistant instructions
- `ARXIV_REFERENCE.md` - ArXiv submission workflow
- `.gitignore` - Clean version control

## File Counts

```bash
# Papers
papers/supportbench/SupportBench.pdf    # 26 pages, 640KB
papers/givecare/GiveCare.pdf            # 41 pages, 1.2MB

# Source files
papers/supportbench/SupportBench.tex    # ~920 lines
papers/givecare/GiveCare.tex            # ~1858 lines

# Figures
papers/supportbench/figures/            # 12 PDFs
papers/givecare/figures/                # 14 PDFs

# Benchmark code
benchmark/scenarios/                     # 13 JSON files (tier1/, tier2/, tier3/)
benchmark/configs/                       # YAML configurations
benchmark/supportbench/                  # Python package (~2000 lines)
```

## Quick Actions

### Compile Papers
```bash
# SupportBench
cd papers/supportbench && pdflatex SupportBench.tex

# GiveCare
cd papers/givecare && pdflatex GiveCare.tex
```

### Run Benchmark
```bash
# Minimal test (5 minutes)
python benchmark/scripts/validation/run_minimal.py \
  --scenario benchmark/scenarios/tier1/crisis.json \
  --model google/gemini-2.5-flash

# Full evaluation (30-40 minutes, $12-15)
python benchmark/scripts/validation/run_full.py --all-tiers
```

### Regenerate Figures (Optional)
```bash
# SupportBench
cd papers/supportbench && python figures/generate_paper1_BEST_FINAL.py

# GiveCare
cd papers/givecare && python scripts/generate_figures.py
```

## Git Status

Repository is clean and ready for:
- ✓ GitHub push
- ✓ arXiv submission (LaTeX sources + PDFs)
- ✓ OpenReview upload (PDFs)
- ✓ Community collaboration

## Next Steps

1. **Immediate**: Papers ready for submission as-is
2. **Optional**: 1-hour figure polish (see `docs/submission-guides/FIGURE_REGENERATION_GUIDE.md`)
3. **Post-submission**: Run full 13-scenario evaluation for camera-ready versions

---

Last cleaned: 2025-11-03  
Status: ✅ PRODUCTION READY
