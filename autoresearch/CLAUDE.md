# autoresearch

Autonomous experiment loop for InvisibleBench improvement. Inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch).

## How it works

```
program.md (campaign instructions)
     ↓
start.sh → run_experiment.sh → run_scenario.sh
     ↓              ↓                ↓
  init          for each          3 probe models
  baseline      scenario          score + spread
                    ↓
              compare.py → commit or revert
```

## Locked files (DO NOT MODIFY during experiments)

- `constants.py` — probe models, thresholds, budget limits
- Scoring rules in `benchmark/configs/` — judge prompts, weights
- Scorer code in `benchmark/invisiblebench/evaluation/scorers/`

Changing these invalidates all prior results.

## Mutable (agent edits)

- `benchmark/scenarios/**/*.json` — scenario content (what gets optimized)
- `program.md` — campaign instructions (swap for different research tracks)

## Commands

```bash
# Analyze current spreads
python autoresearch/analyze_spread.py

# Run one scenario through 3 probe models
./autoresearch/run_scenario.sh benchmark/scenarios/safety/crisis/dual_concern_crisis.json

# Compare results and decide commit/revert
python autoresearch/compare.py results/autoresearch/run_*/all_results.json

# Full autonomous loop
./autoresearch/start.sh

# Generate before/after spread chart
python autoresearch/generate_chart.py                  # From REPORT.md → chart.png
python autoresearch/generate_chart.py --json data.json # From JSON

# Post session report to GitHub Discussions after campaign
./scripts/post_discussion.sh autoresearch              # Post (auto-generates chart)
./scripts/post_discussion.sh autoresearch --dry-run    # Preview
```

## Results

- `results/` — experiment JSONs (per-run)
- `experiment_log.md` — append-only audit trail
- `REPORT.md` — campaign summary (written at end)

## Campaigns

| Campaign | program.md | Metric | Status |
|----------|-----------|--------|--------|
| Scenario differentiation | Current | Score spread (max-min across 3 probes) | 5/11 improved |
