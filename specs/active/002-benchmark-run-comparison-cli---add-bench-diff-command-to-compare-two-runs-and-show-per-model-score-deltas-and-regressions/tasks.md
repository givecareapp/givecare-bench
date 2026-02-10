# Tasks: Benchmark Run Comparison CLI - Add bench diff command to compare two runs and show per-model score deltas and regressions

## 1. Setup
- [x] 1.1 Flesh out spec/proposal/tasks placeholders for `bench diff`

## 2. Implementation
- [ ] 2.1 Add `bench diff` subcommand wiring in `benchmark/invisiblebench/cli/runner.py`
- [ ] 2.2 Implement run reference resolution (run dir, `all_results.json` path, run ID prefix)
- [ ] 2.3 Implement aggregation + diff (per-model overall score delta, pass/fail/error counts)
- [ ] 2.4 Implement terminal output (table) and regression highlighting

## 3. Testing
- [ ] 3.1 Add unit tests for diff logic using fixtures in `benchmark/tests/fixtures/`
