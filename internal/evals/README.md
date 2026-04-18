# Internal Evaluation Artifacts

Judge validation and scorer analysis for InvisibleBench.

## Status

Public hard-fail validation is now landed on the resolved 60-trace gold set. External artifacts (run results, private trace files) are still required to reproduce the full validation pipeline, and quality-judge validation remains in progress. These are not included in the public repo.

## Judge statuses

Safety and compliance are now validated on the resolved 60-trace gold set for the public hard-fail layer. Regard remains **fixed-unvalidated**; deterministic scorers remain contract-driven rather than human-judged.

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
| `verifier/` | Active verifier rubric, prompts, scenario contracts, corpus manifest, resolved gold labels, and scorer/verifier validation artifacts |
| `traces_for_labeling*.json` | Stratified trace samples for human review |

## Archived bundles

Historical remediation material from the 2026-03-31 scorer cleanup now lives in:

- `archive/internal/evals/remediation_2026-03-31/` — audit, stabilization plan, checklist, false-scope inventory/examples, spot check, and old review UI
- `archive/internal/evals/verifier/` — archived verifier memos and tranche outputs from the same remediation window
