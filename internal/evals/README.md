# Internal Evaluation Artifacts

Judge validation and scorer analysis for InvisibleBench.

## Status

Human-label validation is **in progress**. External artifacts (run results, private trace files) are required to reproduce the validation pipeline. These are not included in the public repo.

## Judge statuses

All judges remain **unvalidated** or **fixed-unvalidated** until human-label validation is rerun and recorded against the current scorer versions.

## External dependencies

- `results/run_20260213_232236/all_results.json` — source traces for labeling (not committed)
- Private confidential scenario results — loaded from `INVISIBLEBENCH_PRIVATE_CONFIDENTIAL_SCENARIOS_DIR`

## Active contents

| File | Purpose |
|------|---------|
| `config.json` | Phase tracking and sample stratification |
| `annotation_rubric.md` | Human labeling rubric |
| `design_learnings.md` | Scorer design decisions |
| `error_analysis.md` | False positive/negative analysis |
| `meta_judge/` | Judge-of-judge evaluation traces reserved from the golden-set sample |
| `verifier/` | Active verifier rubric, prompts, scenario contracts, corpus manifest, and golden-set calibration work |
| `traces_for_labeling*.json` | Stratified trace samples for human review |

## Archived bundles

Historical remediation material from the 2026-03-31 scorer cleanup now lives in:

- `archive/internal/evals/remediation_2026-03-31/` — audit, stabilization plan, checklist, false-scope inventory/examples, spot check, and old review UI
- `archive/internal/evals/verifier/` — archived verifier memos and tranche outputs from the same remediation window
