# Internal Evaluation Artifacts

Judge validation and scorer analysis for InvisibleBench.

## Status

Human-label validation is **in progress**. External artifacts (run results, private trace files) are required to reproduce the validation pipeline. These are not included in the public repo.

## Judge statuses

All judges remain **unvalidated** or **fixed-unvalidated** until human-label validation is rerun and recorded against the current scorer versions.

## External dependencies

- `results/run_20260213_232236/all_results.json` — source traces for labeling (not committed)
- Private confidential scenario results — loaded from `INVISIBLEBENCH_PRIVATE_CONFIDENTIAL_SCENARIOS_DIR`

## Contents

| File | Purpose |
|------|---------|
| `config.json` | Phase tracking and sample stratification |
| `annotation_rubric.md` | Human labeling rubric |
| `design_learnings.md` | Scorer design decisions |
| `error_analysis.md` | False positive/negative analysis |
| `benchmark_audit_2026-03-31.md` | Benchmark-level audit of the current board and scoring contract |
| `benchmark_stabilization_plan_2026-03-31.md` | Broad stabilization plan for the benchmark and artifacts |
| `meta_judge/` | Judge-of-judge evaluation traces |
| `verifier/` | Consolidated verifier rubric, prompts, scenario contracts, corpus manifest, retrospective, and remediation plan |
| `traces_for_labeling*.json` | Stratified trace samples for human review |
