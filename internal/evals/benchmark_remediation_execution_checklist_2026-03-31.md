Diátaxis: how-to

# How to execute benchmark remediation to completion

This is the task-based execution plan for taking the benchmark from the current 2026-03-31 diagnostic state to a publishable corrected release.

Use this as the working checklist.

## Goal

Complete scorer remediation, frozen-corpus rescoring, artifact cleanup, and selective reruns until the benchmark is ready to be republished with a defensible public contract.

## Definition of done

The work is only done when **all** of the following are true:

- `false_scope_or_capability_claim` no longer dominates compliance failures by sheer breadth alone
- honest limitation statements no longer hard-fail by default
- known false positives are covered by regression tests
- clear medical and safety true positives are preserved
- frozen runs have been rescored with the corrected scorer
- raw and gated quality are both exposed in artifacts
- contaminated models are rerun or explicitly flagged in the publishable output
- a before/after benchmark note exists showing what changed and why the new release is more trustworthy

## Operating rules

1. Do **not** run a fresh full benchmark during remediation.
2. Treat the frozen corpus as the source of truth for scorer work.
3. Every task must produce an artifact, test result, or written evidence.
4. Do not advance a phase unless its exit criteria are met.
5. If rescoring reveals a regression, loop back to the scorer phase instead of pushing forward.

## Frozen corpus

Work from these local assets:

- `results/run_20260330_021307/`
- `results/partial_runs/run_20260330_033649_up_to_deepseek/`
- `results/run_20260330_130332/`
- `results/leaderboard_ready/`

## Phase 0 — Lock the workspace

### Tasks

- [x] Confirm the frozen run directories exist locally and are readable
- [x] Make a local backup if needed
- [x] Record the current baseline counts from the audit in a working note
- [x] Record the current contaminated models list

### Outputs

- local backup or explicit note that backup was skipped intentionally
- baseline note with:
  - `172` `false_scope`-involved compliance failures
  - `154` `false_scope`-only hard fails
  - `135/750`
  - `115/261`
  - `95/172`
  - contaminated models: `Qwen3.5 35B`, `Qwen3.5 397B`, `GPT-5 Mini`, `Kimi K2.5`

### Exit criteria

- frozen corpus is confirmed available
- baseline metrics are written down and frozen for comparison

## Phase 1 — Exhaust the `false_scope` corpus

### Tasks

- [x] Enumerate every `false_scope_or_capability_claim` hit across the frozen corpus
- [x] Separate rows into:
  - [x] `false_scope` only
  - [x] `false_scope` plus other hard fails
  - [x] inaccessible/missing-detail contaminated rows
- [x] For each accessible row, label the subtype:
  - [x] explicit false privacy/control claim
  - [x] false therapist/licensure claim
  - [x] false memory/platform guarantee
  - [x] vague or soft boundary issue
  - [x] honest limitation statement
  - [x] anti-dependency / non-personhood honesty
- [x] Pull representative examples for each subtype
- [x] Identify the exact rows showing contract inversion

### Recommended working artifacts

- `internal/evals/false_scope_inventory_2026-03-31.csv`
- `internal/evals/false_scope_examples_2026-03-31.md`
- `internal/evals/false_scope_contract_inversion_2026-03-31.md`

### Exit criteria

- every accessible `false_scope` row is labeled
- inaccessible rows are explicitly listed, not silently dropped
- there is a clean set of examples for true positives vs false positives

## Phase 2 — Build the regression corpus

### Tasks

- [x] Select canonical false-positive cases from the frozen corpus
- [x] Select canonical true-positive hard-fail cases from the frozen corpus
- [x] Select canonical soft-boundary cases that should not gate the trace
- [x] Turn those into minimal test fixtures or direct test inputs
- [x] Add failing tests first for the known false positives

### Minimum must-cover cases

- [x] `context_regulatory_data_privacy_001`
- [x] `context_regulatory_misrepresentation_001`
- [x] `tier1_scope_honesty_001`
- [x] `tier2_attachment_001`
- [x] `tier3_longitudinal_001`

### True-positive preservation set

Include cases that should continue to hard fail for things like:

- [x] false confidentiality guarantee
- [x] false deletion/control guarantee
- [x] false therapist/counselor claim
- [x] false memory/platform guarantee presented as fact
- [x] actual medical/treatment directive behavior

### Target file

- `benchmark/tests/unit/test_scorers/test_compliance.py`

### Exit criteria

- failing tests exist for the known false positives before the scorer patch
- true-positive preservation tests are also present

## Phase 3 — Patch the scorer contract

### Tasks

- [x] Split `false_scope_or_capability_claim` logic into three classes:
  - [x] public hard fail
  - [x] soft boundary violation
  - [x] allowed honest limitation
- [x] Remove or constrain any path where `scope_accurate = false` alone becomes a public hard fail
- [x] Ensure contract inversion cases no longer produce hard fails by side path alone
- [x] Keep clear explicit deception cases as hard fails
- [x] Review whether supporting updates are needed in:
  - [x] `src/invisiblebench/evaluation/schemas/compliance.py`
  - [ ] `benchmark/configs/scoring.yaml`
  - [x] `benchmark/configs/prompts/compliance_framework.txt`

### Primary code target

- `src/invisiblebench/evaluation/scorers/compliance.py`

### Exit criteria

- regression tests pass
- false-positive cases stop hard-failing
- explicit deceptive cases still hard-fail

## Phase 4 — Verify locally before rescoring

### Tasks

- [x] Run unit tests for compliance scoring
- [x] Manually inspect a small sample of previously bad traces
- [x] Confirm the scorer no longer generates the known inversion pattern on those traces
- [x] Fix the success-threshold mismatch before treating rescore outputs as canonical

### Important note

Resolve the threshold mismatch first:

- main result model uses `0.6`
- `rescore.py` currently uses `0.5`

### Exit criteria

- unit tests are green
- manual spot-checks match the intended rule split
- threshold behavior is aligned

## Phase 5 — Rescore the frozen corpus

### Tasks

- [x] Rescore `results/run_20260330_021307/`
- [ ] Rescore `results/partial_runs/run_20260330_033649_up_to_deepseek/`
- [ ] Rescore `results/run_20260330_130332/`
- [ ] Generate before/after comparisons for:
  - [ ] total hard-fail count
  - [ ] compliance-fail count
  - [ ] `false_scope`-involved count
  - [ ] `false_scope`-only count
  - [ ] category pass rates
  - [ ] model rank shifts
  - [ ] preserved medical/safety true positives

### Recommended artifact

- `internal/evals/rescore_comparison_2026-03-31.md`

### Exit criteria

- rescored outputs exist for all frozen runs
- false positives are materially reduced
- true positives are preserved well enough to continue

### Loop-back rule

If false positives remain high or true positives collapse, go back to **Phase 3**.

## Phase 6 — Unmask raw vs gated quality

### Tasks

- [x] Update artifact generation so both raw and gated quality are retained
- [x] Expose at least:
  - [x] `raw_regard`
  - [x] `raw_coordination`
  - [x] `gated_regard`
  - [x] `gated_coordination`
- [x] Update any affected summaries/reports/exports
- [x] Add tests for artifact shape if needed

### Primary target

- `src/invisiblebench/results_io.py`

### Exit criteria

- artifacts clearly separate raw quality from gate-masked quality
- summaries no longer present masked values as if they were raw quality

## Phase 7 — Rerun contaminated models only

### Tasks

Rerun in this order:

- [ ] `Qwen3.5 35B`
- [ ] `Qwen3.5 397B`
- [ ] `GPT-5 Mini`
- [ ] `Kimi K2.5`

For each rerun:

- [ ] confirm provider/runtime health
- [ ] confirm scenario count completeness
- [ ] confirm comparability metadata
- [ ] merge into corrected leaderboard artifacts or flag explicitly if rerun is not possible

### Exit criteria

- contaminated models are rerun successfully or clearly flagged in the release output

## Phase 8 — Publishable release check

### Tasks

- [ ] Write a before/after release note describing what changed
- [ ] Record the final hard-fail taxonomy
- [ ] Record remaining limitations honestly
- [ ] Confirm the benchmark is being presented as a scorecard, not an oversimplified single scalar
- [ ] Confirm release artifacts point to the corrected scorer version only

### Recommended artifact

- `internal/evals/release_readiness_2026-03-31.md`

### Exit criteria

- the release note explains why the updated board is more trustworthy
- the benchmark meets the definition of done at the top of this file

## Closed-loop execution rule

Run the project with this loop:

1. pick the highest-priority unchecked task in the current phase
2. complete it and produce evidence
3. update counts/tests/docs immediately
4. check the phase exit criteria
5. if the phase is not complete, take the next task in the same phase
6. if rescoring exposes a regression, go back to the scorer phase
7. stop only when the definition of done is satisfied

## Fastest practical path

If execution speed matters most, do the next tasks in exactly this order:

1. enumerate and label all remaining `false_scope` traces
2. add regression tests for the five known false-positive scenarios
3. patch `src/invisiblebench/evaluation/scorers/compliance.py`
4. fix threshold inconsistency for rescoring
5. rescore the frozen runs
6. separate raw vs gated quality in artifacts
7. rerun contaminated models only
8. write the release-readiness note
