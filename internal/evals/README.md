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
| `baseline_metrics_2026-03-31.md` | Frozen-corpus baseline metrics captured at remediation start |
| `benchmark_remediation_execution_checklist_2026-03-31.md` | Task-based execution plan for taking the benchmark to a publishable corrected release |
| `false_scope_contract_inversion_2026-03-31.md` | Audit of contract-inversion cases on the false-scope axis |
| `false_scope_examples_2026-03-31.md` | Representative false-scope hard-fail examples from the frozen corpus |
| `false_scope_inventory_2026-03-31.csv` | Full false-scope board-row inventory with row classification and quotes |
| `manual_scope_spotcheck_2026-03-31.md` | Post-patch scope-remediation spot-check on representative transcripts |
| `meta_judge/` | Judge-of-judge evaluation traces |
| `verifier/` | Consolidated verifier rubric, prompts, scenario contracts, corpus manifest, retrospective, and remediation plan |
| `traces_for_labeling*.json` | Stratified trace samples for human review |
