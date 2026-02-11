# Log: Benchmark Run Comparison CLI - Add bench diff command to compare two runs and show per-model score deltas and regressions

## 2026-02-01
- Spec created

### Iteration 1 - 04:01:40
Task: 2.1 Add `bench diff` subcommand wiring in `benchmark/invisiblebench/cli/runner.py`
Result: ✓ Complete

### Iteration 2 - 04:02:44
Task: 2.2 Implement run reference resolution (run dir, `all_results.json` path, run ID prefix)
Result: ✓ Complete

### Iteration 3 - 04:04:17
Task: 2.3 Implement aggregation + diff (per-model overall score delta, pass/fail/error counts)
Result: ✓ Complete

### Iteration 4 - 04:05:35
Task: 2.4 Implement terminal output (table) and regression highlighting
Result: ✓ Complete

### Iteration 5 - 04:06:42
Task: 3.1 Add unit tests for diff logic using fixtures in `benchmark/tests/fixtures/`
Result: ✓ Complete

## Result: SUCCESS
### Verification: PASSED
