# InvisibleBench Reports

Daily benchmark reports capturing model evaluations, findings, and scoring updates.

## Structure

```
reports/
├── README.md                 # This file
├── YYYY-MM-DD/
│   ├── README.md             # Day's summary report
│   └── examples/             # Notable transcripts
│       ├── model-strong-example.md
│       └── model-improvement-example.md
```

## What Each Report Contains

### Summary (README.md)
- Models evaluated that day
- Results table (scores by dimension)
- Per-model analysis:
  - Dimension deltas (e.g., high safety, low trauma)
  - Notable achievements
  - Areas for improvement
- Cross-model patterns
- Scoring fixes or calibration changes (if any)

### Examples
Annotated transcripts showing:
- **Strong examples:** Where a model handled a scenario well
- **Room for improvement:** Where a model could do better, with specific suggestions

## Report Cadence

One report per evaluation day. If no evaluations run, no report needed.

## Historical Context

Reports serve as a changelog for:
1. **Model performance over time** — track improvements across versions
2. **Benchmark calibration** — document scoring fixes and why
3. **Research artifacts** — shareable findings for collaborators
