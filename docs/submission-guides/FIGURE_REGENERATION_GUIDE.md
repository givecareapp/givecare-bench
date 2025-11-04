# Figure Regeneration Guide for Publication Polish

## Quick Summary
Both papers use Python scripts to generate figures. To unify style across papers and add requested improvements, run these commands:

## 1. SupportBench Figures (Unified Style)

```bash
cd papers/supportbench
python figures/generate_paper1_BEST_FINAL.py

# Regenerate main figures
pdflatex SupportBench.tex
```

**What this does:**
- Ensures consistent color palette (gcOrange, gcLightPeach, gcTan)
- Standardizes font sizes (10pt minimum for readability)
- Matches heatmap styling across papers

## 2. GiveCare Figures (Add Flow Arrows to Figure 1)

**Target**: Add data flow arrows and trigger labels to Figure 1 (7-component architecture)

### Option A: Quick Fix via Annotations (5 minutes)

Edit `papers/givecare/scripts/generate_figures.py` around line 50-100 (Figure 1 generation):

```python
# Add after component boxes are drawn
# Crisis handoff arrow
ax.annotate('', xy=(crisis_x, crisis_y), xytext=(main_x, main_y),
            arrowprops=dict(arrowstyle='->', lw=2, color='red'))
ax.text(arrow_mid_x, arrow_mid_y, 'crisis keywords\n988, help',
        fontsize=8, color='red', ha='center')

# Assessment handoff arrow  
ax.annotate('', xy=(assess_x, assess_y), xytext=(main_x, main_y),
            arrowprops=dict(arrowstyle='->', lw=2, color='blue'))
ax.text(arrow_mid_x, arrow_mid_y, 'startAssessment\ntool call',
        fontsize=8, color='blue', ha='center')
```

Then regenerate:
```bash
cd papers/givecare
python scripts/generate_figures.py
pdflatex GiveCare.tex
```

### Option B: Manual Diagram Edit via Inkscape (10 minutes)

1. Open `papers/givecare/figures/fig1_architecture.pdf` in Inkscape
2. Add arrows:
   - Red arrow: Main Agent → Crisis Agent (label: "crisis keywords")
   - Blue arrow: Main Agent → Assessment Agent (label: "startAssessment tool")
   - Green arrows: Bidirectional data flow between agents and GiveCareContext
3. Save as PDF, replace original figure
4. Recompile: `pdflatex GiveCare.tex`

## 3. Unified Color Palette (Both Papers)

Both papers already define:
```latex
\definecolor{gcOrange}{RGB}{233, 116, 81}
\definecolor{gcLightOrange}{RGB}{242, 177, 121}
\definecolor{gcTan}{RGB}{217, 184, 151}
\definecolor{gcLightPeach}{RGB}{255, 242, 230}
```

**Verify consistency**: Search for any `\color{` or `RGB` that doesn't use these names.

```bash
# Check for rogue colors
grep -r "\\\\color{" papers/ | grep -v "gcOrange\|gcLightOrange\|gcTan\|gcLightPeach"
```

## 4. Font Size Audit (Print Legibility)

Minimum 10pt for all figure text. Check with:

```bash
# Find figure generation font sizes
grep -r "fontsize=" papers/*/scripts/*.py | grep -v "fontsize=[1-9][0-9]\|fontsize=1[0-9]"
```

Fix any fontsize <10 in Python scripts, then regenerate.

## 5. Optional: GiveCare One-Page Graphical Overview

**Requested**: SMS → agents → SDOH → resources with 2 metrics (latency, N)

Create new figure `fig_overview.pdf`:

```python
# papers/givecare/scripts/generate_overview.py
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(figsize=(10, 4))

# SMS input box
sms = FancyBboxPatch((0, 1.5), 1, 1, boxstyle="round,pad=0.1", 
                      edgecolor='black', facecolor='lightblue')
ax.add_patch(sms)
ax.text(0.5, 2, 'SMS\nInput', ha='center', va='center', fontsize=12, weight='bold')

# Multi-agent box
agents = FancyBboxPatch((2, 1), 2, 2, boxstyle="round,pad=0.1",
                         edgecolor='black', facecolor='lightgreen')
ax.add_patch(agents)
ax.text(3, 2, 'Multi-Agent\n(Main/Crisis/Assess)', ha='center', fontsize=10)

# SDOH box
sdoh = FancyBboxPatch((5, 1.5), 1.5, 1, boxstyle="round,pad=0.1",
                       edgecolor='black', facecolor='lightyellow')
ax.add_patch(sdoh)
ax.text(5.75, 2, 'GC-SDOH-28\n8 domains', ha='center', fontsize=10)

# Resources box
resources = FancyBboxPatch((7.5, 1.5), 1.5, 1, boxstyle="round,pad=0.1",
                            edgecolor='black', facecolor='lightcoral')
ax.add_patch(resources)
ax.text(8.25, 2, 'Resource\nMatching', ha='center', fontsize=10)

# Arrows
ax.annotate('', xy=(2, 2), xytext=(1, 2), arrowprops=dict(arrowstyle='->', lw=2))
ax.annotate('', xy=(5, 2), xytext=(4, 2), arrowprops=dict(arrowstyle='->', lw=2))
ax.annotate('', xy=(7.5, 2), xytext=(6.5, 2), arrowprops=dict(arrowstyle='->', lw=2))

# Metrics
ax.text(5, 0.2, '950ms latency | N=8, 144 conversations', 
        ha='center', fontsize=11, weight='bold', 
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

ax.set_xlim(-0.5, 10)
ax.set_ylim(0, 3.5)
ax.axis('off')
plt.tight_layout()
plt.savefig('../figures/fig_overview.pdf', dpi=300, bbox_inches='tight')
```

Run:
```bash
cd papers/givecare/scripts
python generate_overview.py
```

Add to LaTeX after abstract:
```latex
\begin{figure}[h]
\centering
\includegraphics[width=0.9\textwidth]{figures/fig_overview.pdf}
\caption{GiveCare system overview: SMS-first architecture with multi-agent orchestration, 
caregiver-specific SDOH assessment, and resource matching. Pilot: 950ms median latency, 
N=8 caregivers, 144 conversations.}
\label{fig:overview}
\end{figure}
```

## Compilation Checklist

After any figure changes:

```bash
# SupportBench
cd papers/supportbench
pdflatex SupportBench.tex && pdflatex SupportBench.tex  # Twice for refs

# GiveCare
cd papers/givecare  
pdflatex GiveCare.tex && pdflatex GiveCare.tex

# Verify
pdfinfo supportbench/SupportBench.pdf | grep Pages
pdfinfo givecare/GiveCare.pdf | grep Pages
```

## Time Estimates

- **Tier-dependent table**: ✅ Done (5 min)
- **Quick-start box**: ✅ Done (5 min)
- **Color audit**: 10 min
- **Font size fixes**: 15 min  
- **Figure 1 arrows** (Option A): 20 min
- **Figure 1 arrows** (Option B): 10 min
- **One-page overview**: 30 min

**Total remaining**: ~1 hour for full polish

## When to Skip

If submitting to a workshop/short track, **skip figure regeneration**. Papers are publication-ready as-is. 

If targeting CHI/IMWUT/NeurIPS Datasets Track, **invest the hour** for maximum reviewer clarity.
