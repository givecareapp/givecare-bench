# Benchmark Publishing Audit

InvisibleBench publishes benchmark work in two linked phases:

1. **Code documentation** — the benchmark contract, scorer mechanics, verifier
   routing, calibration status, and release commands are documented in the repo
   before the results are treated as public claims.
2. **Result narrative** — the generated benchmark outputs are QA-gated, reduced
   into a web payload, and presented as caregiver-centered failure-mode analysis.

This split is intentional. The benchmark should not read as a generic stack
rank of models. The useful claim is sharper: it shows where each model is jagged
in caregiver-support conversations, which failures are acute safety or scope
problems, and which weaknesses are communication or coordination patterns that
would make a caregiver AI feel brittle in practice.

## Phase 1: Code Documentation

The code documentation phase makes the procedure inspectable:

- `benchmark/configs/failure_modes.yaml` defines the active 53-check failure
  inventory across safety, compliance, communication, coordination, and boundary
  integrity.
- `benchmark/configs/scorer_routing.yaml` records which checks use
  deterministic, LLM, or corpus scorer routes.
- `benchmark/configs/verifier_prompts/` holds the per-check verifier prompts.
- `src/invisiblebench/evaluation/mode_engine.py` aggregates per-check verdicts
  into hard-fail, dimension, blind-spot, and overall artifacts.
- `scripts/run_scan.py`, `scripts/generate_leaderboard.py`,
  `scripts/qa_leaderboard.py`, and `scripts/sync_web_bench_leaderboard.py`
  form the release path from transcripts to public web payload.

The publication standard is evidence-bearing: each failure should preserve the
eligible check, the verdict, the scorer route, and quoted transcript evidence.
The code docs should make it possible to audit how a public claim was produced
without relying on a single opaque LLM judge.

## Phase 2: Results And Scoring Narrative

The result phase starts from the canonical leaderboard artifact:

- Source: `data/leaderboard/leaderboard.json`
- Current source artifact: `results/v3_scan/merged_phase2/per_run.jsonl`
- Current public benchmark version: `3.1.0`
- Current publication stage: `v3-alpha`
- Current public scan: 11 models × 63 scenarios × 53 active checks
- Current generated timestamp: `2026-05-15T17:42:58Z`

The web-bench payload is a smaller projection of that artifact:

- Target: `../gc-web/apps/web-bench/public/bench/leaderboard.json`
- Payload shape: `metadata`, `models`, and `findings`
- Findings include A8 false reassurance, D2 infodump, hardest scenarios,
  thematic failure clusters, contrast sets, and field-relative model signatures.

The projected web surface should explain model differences, not flatten them.
Its public analysis is organized around four layers:

1. **Reading protocol** — hard gates first, failure modes second, rank last.
2. **Theme audit** — universal, jagged, and emerging failure patterns.
3. **Contrastive pairs** — matched caregiver pressure with divergent model
   behavior and quoted transcript evidence.
4. **Model signatures** — per-model deployment reads combining safety tier,
   category strengths/weaknesses, hard-fail evidence, and repeating blind spots.

Useful public analysis asks:

- Which safety or scope gates failed, and with what evidence?
- Which failure modes are concentrated in one model versus field-wide?
- Which models are safe but operationally cold, warm but boundary-risky, or
  strong in one caregiver pattern and weak in another?
- Which contrast-set siblings reveal sensitivity to wording, scenario framing,
  or caregiver-recipient relationship dynamics?

That is the Web-bench narrative contract: expose the shape of model behavior in
caregiver AI, especially the non-obvious jagged edges that aggregate scores hide.

## Claim Posture

The strongest public claims are hard-fail rates, safety/compliance gate behavior,
and evidence-backed failure signatures. Overall score and rank are secondary
navigation aids. They should not be the main story unless two models have similar
hard-fail surfaces and the comparison is framed as exploratory.

Avoid claims like "best caregiver model." Prefer claims like:

- "clean safety gates but weak presence-without-action behavior"
- "strong communication but recurring crisis-signal negation"
- "low hard-fail rate with a narrow recipient-aggression blind spot"
- "safe on direct ideation but brittle on masked caregiver-collapse language"

This keeps the benchmark aligned with its purpose: a caregiver AI-centered audit
of strengths, weaknesses, and deployment-relevant failure mechanics.
