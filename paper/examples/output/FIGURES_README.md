# GiveCare Paper Figure Generation

This directory contains scripts and assets for generating publication-quality figures for the GiveCare system paper.

## Generated Figures

All figures are generated as vector graphics (PDF) for optimal quality in LaTeX compilation.

### Figure List

1. **fig6_multiagent_architecture.pdf** - Multi-agent architecture with seamless handoffs
   - Shows Main, Crisis, and Assessment agents
   - Displays GiveCareContext shared state
   - Illustrates Twilio SMS integration and OpenAI GPT-5 nano API calls

2. **fig7_gcsdoh_domains.pdf** - GC-SDOH-28 domain breakdown
   - Left: Question distribution across 8 domains (pie chart)
   - Right: Need prevalence in beta cohort (N=144, horizontal bar chart)

3. **fig8_burnout_scoring.pdf** - Composite burnout scoring system
   - Left: Assessment weights (EMA 40%, CWBS 30%, REACH-II 20%, SDOH 10%)
   - Right: Exponential temporal decay (τ = 10 days)

4. **fig9_beta_results.pdf** - Beta performance heatmap
   - LongitudinalBench dimension scores (0-1 scale)
   - Shows performance across 8 evaluation dimensions

5. **fig10_dspy_optimization.pdf** - DSPy optimization results
   - P1-P6 trauma-informed principle scores
   - Baseline (81.8%) vs. Optimized (89.2%)
   - Shows +9.0% improvement breakdown

## Requirements

```bash
pip install matplotlib seaborn numpy
```

For LaTeX-quality text rendering (optional):
```bash
# macOS
brew install --cask mactex

# Ubuntu/Debian
sudo apt-get install texlive-full

# Then set text.usetex = True in generate_figures.py
```

## Usage

### Generate all figures
```bash
python3 generate_figures.py
```

### Generate individual figures
Edit `generate_figures.py` and comment out unwanted function calls in `main()`.

## Color Palette

Figures use a colorblind-friendly palette:

- **Primary (Blue)**: `#2E86AB` - Main elements, charts
- **Secondary (Purple)**: `#A23B72` - Agents, LLM connections
- **Accent (Orange)**: `#F18F01` - Highlights, handoffs
- **Success (Green)**: `#06A77D` - Positive metrics, improvements
- **Warning (Red)**: `#D84315` - Crisis, alerts
- **Neutral (Gray)**: `#6C757D` - Secondary text, user elements

## LaTeX Integration

All figures are referenced in `paper3_givecare_system.tex`:

```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=0.8\textwidth]{fig6_multiagent_architecture.pdf}
\caption{Your caption here}
\label{fig:multiagent}
\end{figure}
```

## System Flow Diagram

A Mermaid flowchart (`system_flow.mmd`) is also provided for interactive viewing:

```bash
# View in GitHub (renders automatically)
# Or convert to image:
mmdc -i system_flow.mmd -o system_flow.svg
```

## Customization

### Changing Colors
Edit the `COLORS` dict in `generate_figures.py`:

```python
COLORS = {
    'primary': '#2E86AB',
    'secondary': '#A23B72',
    # ...
}
```

### Adjusting Figure Sizes
Modify `figsize` parameter in each function:

```python
fig, ax = plt.subplots(figsize=(10, 6))  # width, height in inches
```

### Font Settings
Edit the `plt.rcParams.update({...})` block for global font changes.

## Troubleshooting

### Figures look pixelated
- Ensure you're using PDF output (`savefig.format': 'pdf'`)
- Check DPI settings (`figure.dpi': 300`)

### LaTeX compilation errors
- Verify all figure files are in the same directory as the .tex file
- Check figure labels match `\ref{...}` commands in text

### Missing dependencies
```bash
pip install --upgrade matplotlib seaborn numpy
```

## File Organization

```
output/
├── generate_figures.py       # Main generation script
├── system_flow.mmd           # Mermaid flowchart
├── fig6_multiagent_architecture.pdf
├── fig7_gcsdoh_domains.pdf
├── fig8_burnout_scoring.pdf
├── fig9_beta_results.pdf
├── fig10_dspy_optimization.pdf
└── paper3_givecare_system.tex
```

## Future Improvements

Planned enhancements:
- [ ] TikZ/PGF output via tikzplotlib for native LaTeX rendering
- [ ] Animated versions for presentations (using matplotlib animation)
- [ ] Interactive HTML versions for supplementary materials
- [ ] Automated figure regeneration on data updates
- [ ] CI/CD integration for figure validation

## References

- Matplotlib documentation: https://matplotlib.org/stable/
- Seaborn gallery: https://seaborn.pydata.org/examples/index.html
- LaTeX graphics guide: https://www.overleaf.com/learn/latex/Inserting_Images
- Colorblind-friendly palettes: https://colorbrewer2.org/
