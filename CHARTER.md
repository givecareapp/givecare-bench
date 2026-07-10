# gc-bench Charter

This charter is an evaluation document, not an operating manual. For the shared
GiveCare North Star, see `~/wiki/pages/givecare/givecare-system.md`.

## Purpose

`gc-bench` owns InvisibleBench: GiveCare's public benchmark for measuring how AI
systems handle caregiving **Safety** (hard lines it must not cross) and **Care**
(how it shows up for the caregiver). Output model: `safety-care/v1` — two layers
reported side by side, never composited (see `docs/ontology.md`).

## Role In GiveCare

`gc-bench` belongs to the evaluation layer and open-source credibility domain. It
turns GiveCare's safety thesis into inspectable scenarios, failure modes,
verifiers, scans, calibration evidence, and public leaderboard artifacts. It
feeds the product learning loop without becoming the product runtime.

## Product / System Promise

The repo should make safety claims testable. It should expose model jaggedness in
caregiving contexts, preserve calibrated hard-fail checks, and create credible
pressure that improves Mira, public communication, and future model training.

## What This Repo Owns

- InvisibleBench public benchmark scenarios, configs, taxonomy, verifier prompts,
  runner, scan tooling, calibration artifacts, and leaderboard generation.
- `checks/<layer>/<dimension>/<ID>.yaml` as the benchmark check taxonomy, including definitions and embedded routing.
- Public methodology, findings, architecture, and verifier-validation docs.
- Leaderboard JSON and sync tooling for `../gc-web/apps/web-bench`.
- Import/staging workflows for `../givecare-evals` candidate cases.
- Overnight campaign runner for batch-probing staged scenarios and staging
  passing results to `intake/review/` for morning human review.
- V2 HTTP harness integration for evaluating the live GiveCare product contract.

## What This Repo Does Not Own

- Live SMS policy gates, evaluator enforcement, Convex state, or Mira runtime
  behavior. Those belong in `../gc-sms`.
- Public eval dataset distribution outside the executable benchmark. That belongs
  in `../givecare-evals`.
- Model training runs or checkpoint production. That belongs to
  `givecareapp/givecare-train` (archived on GitHub; fine-tuning is deferred
  and there is no local clone).
- Public web rendering of the benchmark site. That belongs in `../gc-web`.
- Private user traces unless explicitly harvested, anonymized, reviewed, and
  promoted through the accepted benchmark/eval workflow.

## Inputs

- Public benchmark scenarios and failure-mode taxonomy.
- Human-labeled calibration sets and scorer-validation evidence.
- Candidate scenarios from `../givecare-evals`.
- Product traces from `../gc-sms` only after safe harvest/review.
- Model outputs from configured providers and harnesses.

## Outputs

- Scan results, per-run JSONL, verifier judgments, calibration reports,
  leaderboard artifacts, and overnight campaign review candidates.
- Public findings and methodology docs.
- Benchmark pressure that informs `../gc-sms` prompt, navigation, evaluator, and
  policy changes.
- Reward/evaluation signal for `givecareapp/givecare-train` (archived on
  GitHub; no local clone), once fine-tuning resumes.
- Public credibility assets projected by `../gc-web`.

## Core Invariants

- Benchmark data stays in `benchmark/`; runtime code stays in `src/invisiblebench/`.
- Scenario contracts, category names, turn indices, and taxonomy mappings must
  remain strict and validated.
- Safety claim rates from `claim_ready` checks are the only external claim surface.
- Verifier changes require calibration evidence and regression tests.
- Public leaderboard artifacts must pass QA before web sync.
- Confidential or private data must not leak into public scenarios.

## Evaluation Questions

- Does this change make a GiveCare safety claim more measurable, calibrated, or
  externally defensible?
- Does it preserve comparability across models, scenarios, and releases?
- Does it distinguish benchmark truth from product runtime enforcement?
- Are new findings backed by scenario evidence, verifier behavior, and QA gates?
- Does the change feed the learning loop back into `../gc-sms`,
  `../givecare-evals`, `givecareapp/givecare-train` (archived; no local
  clone), or public proof?

## Anti-Patterns

- Publishing new claims from uncalibrated verifier behavior.
- Blurring public benchmark scenarios with private production traces.
- Reintroducing a composite (`overall_score`) or a model rank — the output is a
  jagged Safety/Care profile; the layers are never combined.
- Publishing a `not_claim_ready` check as part of the claim surface — checks
  enter public claims only after independent human-labeled calibration on
  natural cases.
- Adding product-specific behavior requirements directly into benchmark runtime
  code instead of testing them through harness contracts.
- Hand-editing web-bench payloads rather than regenerating/syncing leaderboard
  artifacts.

## Related Documents

- `CLAUDE.md`
- `AGENTS.md`
- `docs/architecture.md`
- `docs/taxonomy.md`
- `docs/methodology.md`
- `docs/verifier-validation.md`
- `~/wiki/pages/givecare/givecare-system.md`
- `~/wiki/pages/givecare/givecare-bench-verifier-implementation.md`
