# Verifier Unit Tests (authored, AI-panel labeled)

> **Diátaxis: reference.** These are **development unit tests, NOT validation.**
> For the validation bar and what can carry a public claim, see
> [verifier-validation.md](verifier-validation.md). This page is deliberately
> separate so authored AI-panel results are never read as validation by table
> proximity.

## What this is

For each calibrated hard-fail check, an authored **counterfactual card set**
(near-balanced, 8 PASS / 12 FAIL) was written *from the rubric*, labeled by an
**AI reference panel** (a GPT-5.5-class model judge + 3 model judges, blind,
consensus), and scored with the production verifier (GPT-5 Mini).

This is a **rubric unit test**. It answers one question: *does the verifier apply
the written rubric correctly on clean, synthetic cards?* It catches
implementation, polarity, parser, and rubric-application bugs.

## What this is NOT

By construction these tests fail every clause of the `claim_ready` bar
(see [verifier-validation.md § Defining claim_ready](verifier-validation.md)):

- cards are **authored from the spec** (not natural model outputs),
- labels are from **models, not independent humans**,
- there is **no human adjudication, no IAA, no precision/recall on real failures**.

So a pass here is **never** evidence of real-world detection and **never** lets a
check carry a public claim. Each check records this in its YAML
`calibration.evidence` block: `grade: authored_ai_unit_test`,
`reference_label_source: ai_model_consensus`, `independent_human_labels: false`,
`natural_cases: false`, `claim_grade: false`.

## Results (2026-06-30)

20 hard-fail checks have an authored unit test. **19 of 20 passed** (verifier
matched the AI-panel consensus on the authored set). The exception:

- `scope.periodic-disclosure` — **failing**: the LLM verifier returns all-UNCLEAR
  on the (multi-hour, timestamped) cards, and the named interval scorer is
  unimplemented. Needs a deterministic interval scorer.

The agreement value per check lives in its YAML under `ai_unit_test_agreement`.
It is recorded as a unit-test signal only; it is **not** reported as a validation
κ and does not appear in the validation manifest's tables.

## How a check leaves this page

A check graduates from "passed the authored unit test" to `claim_ready` only by
clearing the full statistical, human-labeled, natural-case bar in
[verifier-validation.md](verifier-validation.md). The unit test is a
prerequisite-grade sanity check, not a step on the validation ladder.
