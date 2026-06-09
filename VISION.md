# gc-bench Vision

`gc-bench` is InvisibleBench: GiveCare's public benchmark for measuring how AI
systems handle caregiving safety, compliance, communication, coordination, and
boundary failures.

This document is the repo's product and agent decision frame. It explains where
the benchmark is going, what matters now, and which changes are out of bounds.
For ownership and evaluation contracts, see `CHARTER.md`.

## The Product Bet

`gc-bench` makes safety claims testable. It turns GiveCare's safety thesis into
inspectable scenarios, failure modes, verifiers, and a public leaderboard that
exposes model jaggedness in caregiving contexts. The bet is that calibrated,
hard-fail-centered measurement creates credible external pressure that improves
Mira, sharpens public communication, and (eventually) feeds model training.

Hard-fail safety/compliance checks are the primary external claim surface.
Quality scorers and `overall_score` matter, but they are not authoritative until
verifiers are calibrated and validated.

## Current Focus

Priority:

- Calibrated hard-fail checks with verifier-validation evidence and regression
  tests.
- Leaderboard JSON that passes QA before syncing to `../gc-web/apps/web-bench`.
- The V2 HTTP harness that evaluates the live GiveCare product contract.
- The overnight campaign runner staging passing results to `benchmark/review/`
  for morning human review.

Next priorities:

- Importing candidate cases from `../givecare-evals` into staging with
  discipline.
- Feeding benchmark pressure back into `../gc-sms` prompt, navigation,
  evaluator, and policy changes.
- Keeping full-taxonomy coverage (`failure_modes.yaml`) comparable across models
  and releases.

## Calibration Rule

Verifier changes require calibration evidence and regression tests before they
become claims. Keep benchmark data in `benchmark/` and runtime code in
`src/invisiblebench/`. Scenario contracts, category names, turn indices, and
taxonomy mappings stay strict and validated. Product-specific behavior is tested
through harness contracts, not hard-coded into benchmark runtime.

## Repo Boundary

`gc-bench` owns the benchmark scenarios, taxonomy, verifiers, runner, scans,
calibration artifacts, and leaderboard generation. It does not own live SMS
policy/enforcement, public eval dataset distribution, model training runs, or
public web rendering. Full ownership matrix is in `CHARTER.md`.

## Source Of Truth

- Benchmark taxonomy, verifier behavior, and leaderboard truth are canonical
  here.
- Public eval dataset distribution lives in `../givecare-evals`; candidate cases
  flow into staging here.
- Runtime enforcement lives in `../gc-sms`; the benchmark measures it, it does
  not enforce it.
- Web rendering of findings lives in `../gc-web`, synced from leaderboard JSON.

## Evaluation Loop

Every change should make a GiveCare safety claim more measurable, calibrated, or
externally defensible while preserving comparability across models and releases.
Run `uv run pytest benchmark/tests -q`, `uv run ruff check .`, and
`uv run bench doctor`. New findings must be backed by scenario evidence, verifier
behavior, and QA gates.

## Agent Rules

- Do not publish claims from uncalibrated verifier behavior.
- Keep public benchmark scenarios separate from private production traces; harvest
  traces only after anonymization and review.
- Treat hard-fail behavior as more authoritative than `overall_score` until
  quality scorers are validated.
- Test product behavior through harness contracts, not benchmark runtime edits.
- Regenerate and sync leaderboard payloads; never hand-edit the web-bench copy.

## What Not To Build For Now

- New claims from uncalibrated verifiers.
- Private production traces blurred into public scenarios.
- Product-specific requirements baked into benchmark runtime code.
- Hand-edited web-bench payloads.
- Training runs here — reward/evaluation signal feeds `../gc-tune` (archived),
  but checkpoint production stays out of this repo.

## Read Order

- `VISION.md` → benchmark direction, priority frame, and agent guardrails.
- `CHARTER.md` → ownership and evaluation contract.
- `CLAUDE.md` → benchmark architecture, verifier calibration, and CLI.
- `AGENTS.md` → benchmark guardrails and scenario contract.
- `../VISION.md` → ecosystem direction and cross-repo seams.
