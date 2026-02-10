# Proposal: Benchmark Run Comparison CLI - Add bench diff command to compare two runs and show per-model score deltas and regressions

## Intent
Quickly compare two benchmark runs (typically two commits, prompt changes, or scorer changes) to:

- See per-model score deltas at a glance
- Identify regressions (score down, failures up) without manually opening two HTML reports
- Support routine maintenance workflows like `bench health` and leaderboard updates

## Scope
**In scope:**
- New CLI utility: `uv run bench diff <base> <new>`
- Compare two runs by reading their `all_results.json` outputs
- Aggregate per-model metrics from per-scenario rows:
  - Average overall score
  - Count of `status`: `pass`, `fail`, `error` (treat `error` as failure for regression reporting)
  - Count of `hard_fail: true`
- Show deltas from base to new per model and highlight regressions

**Out of scope:**
- Per-scenario diffs and root-cause analysis (that is a follow-on feature)
- Any changes to scoring logic or benchmark execution
- Visualization beyond terminal output (HTML charts, etc.)

## Approach
1. Resolve run references to a concrete `all_results.json` file:
   - Accept a path to `all_results.json`, a run directory containing it, or a run ID/prefix.
2. Load both JSON files (list of result rows).
3. Aggregate rows per model for each run.
4. Compute per-model deltas (new - base) and detect regressions.
5. Print a stable, copy-paste-friendly table suitable for CI logs.
