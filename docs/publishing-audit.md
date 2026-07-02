# Benchmark Publishing Audit

InvisibleBench publishes benchmark work in two linked phases:

1. **Code documentation** — the benchmark contract, scorer mechanics, verifier
   routing, calibration status, and release commands are documented in the repo
   before the results are treated as public claims.
2. **Result narrative** — the generated benchmark outputs are QA-gated, reduced
   into a web payload, and presented as caregiver-centered failure-mode analysis.
   The current checked-in Phase 2 artifact is a non-strict public source until
   current-contract coverage gaps and residual `UNCLEAR` verdicts are
   adjudicated or regenerated and `scripts/qa_leaderboard.py --strict` passes.

This split is intentional. The benchmark should not read as a generic stack
rank of models. The useful claim is sharper: it shows where each model is jagged
in caregiver-support conversations, which failures are acute safety or scope
problems, and which weaknesses are communication or coordination patterns that
would make a caregiver AI feel brittle in practice.

## Phase 1: Code Documentation

The code documentation phase makes the procedure inspectable:

- `checks/` (one YAML per check, organized as `checks/safety/*` and `checks/care/*`) defines the active 50-check failure
  inventory across 4 Safety lines (Crisis, Scope, Identity, Autonomy) and 5 Care qualities
  (Belonging, Attunement, Trauma-awareness, Relational, Advocacy).
- the `routing:` block in each `checks/<layer>/<dimension>/<ID>.yaml` records which checks use
  deterministic, LLM, or corpus scorer routes.
- each check file embeds its judge prompt as a `prompt:` block.
- `src/invisiblebench/evaluation/mode_engine.py` aggregates per-check verdicts
  into Safety gate results, per-line violation rates, Care distributions, and blind-spot flags.
- `scripts/run_scan.py`, `scripts/generate_leaderboard.py`,
  `scripts/qa_leaderboard.py`, and `delivery/sync_web_bench.py`
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
- Current public framework: `safety-care/v1` (non-strict artifact; strict QA
  still blocked by current-contract coverage gaps and residual `UNCLEAR`
  verdicts)
- Current checked-in public scan: 11 models × 63 scenarios × 50 active checks
- Next live `--full` target: 15 models × 64 scenarios × 50 active checks
- Current generated timestamp: read from
  `data/leaderboard/leaderboard.json` at `scan_metadata.generated_at` rather
  than hand-copying it into this doc.
- Current strict QA status: not passing. Non-strict QA passes; strict QA fails
  on one missing current scenario, 77 missing check instances, and four
  residual quality-mode `UNCLEAR` verdicts, so it must not be described as a
  strict-QA-passing leaderboard source.
- Current artifact-validation diagnostics: 1,852 eligible `NOT_APPLICABLE`
  mode verdicts (1,466 Safety-gate), 4 unresolved mode verdicts, 0 Safety-gate
  unresolved verdicts, 0 fail-without-evidence rows, 0 missing prompts, 0
  unavailable verifiers, 0 fatal verifier errors, 21 mode results with scorer
  parse errors, 24 parse errors total, and 118 bounded raw-output diagnostic
  samples.
- The artifact also carries `scan_metadata.artifact_issue_policy`, which
  classifies eligible `NOT_APPLICABLE` as resolved coverage, literal `UNCLEAR`
  as a strict-QA blocker, and scorer parse/truncation counters as retry
  diagnostics whose final resolved verdict remains authoritative.

The web-bench payload is a lean projection of that artifact:

- Target: `../gc-web/apps/web-bench/public/bench/leaderboard.json`
- Payload shape (`safety-care/v1`): `schema`, `notes`, `scan_metadata`, and
  `models` — each model carrying `safety` (per-line violation rates + aggregate)
  and `care` (per-quality distributions). `delivery/sync_web_bench.py` validates
  the source and rejects non-public top-level keys before writing.
- Local projection drift is read-only health state: `bench health` reports when
  the checked-in `data/leaderboard/leaderboard_web.json` lags the canonical
  `data/leaderboard/leaderboard.json`; it does not sync or write the projection.
- No `findings` block: thematic failure clusters, contrast sets, and
  field-relative model signatures are NOT in the lean payload. They are deferred
  to a re-authored Safety/Care artifact-v2.

The projected web surface should explain model differences, not flatten them.
In lean `safety-care/v1` its public analysis is organized as per-model audit cards:

1. **Reading protocol** — Safety violation rates first (claim-bearing only for
   `claim_ready` checks, currently empty), Care distributions second
   (directional/`not_claim_ready`), no rank/composite.
2. **Per-line Safety** — Crisis, Scope, Identity, Autonomy: conditional
   violation rate with 95% CI and eligible-n; low-n lines read "insufficient
   observations" rather than a precise rate.
3. **Per-quality Care** — Belonging, Attunement, Relational, Advocacy as
   directional pass-rate distributions (Trauma-awareness is a named zero-check
   gap, excluded from comparison).

Deferred to a re-authored Safety/Care artifact-v2 (not in lean v1): theme audit
(universal/jagged/emerging), contrastive pairs with transcript evidence, and
per-model signatures.

Useful public analysis asks:

- Which safety or scope gates failed, and with what evidence?
- Which failure modes are concentrated in one model versus field-wide?
- Which models are safe but operationally cold, warm but boundary-risky, or
  strong in one caregiver pattern and weak in another?
- If a contrast artifact is present, which contrast-set siblings reveal
  sensitivity to wording, scenario framing, or caregiver-recipient relationship
  dynamics?

That is the Web-bench narrative contract: expose the shape of model behavior in
caregiver AI, especially the non-obvious jagged edges that aggregate scores hide.

## Claim Posture

The strongest public claims are Safety violation rates (per-line conditional,
calibration-gated), gate behavior, and evidence-backed failure signatures. There
is no composite score and no single rank — the leaderboard payload is
`{safety, care}` (schema `safety-care/v1`). Care distributions are directional
signal and should be presented as such. Model comparisons are framed by blind-spot
overlap and jagged Safety profiles, not point rankings.

Avoid claims like "best caregiver model." Prefer claims like:

- "clean safety gates but weak presence-without-action behavior"
- "strong communication but recurring crisis-signal negation"
- "low hard-fail rate with a narrow recipient-aggression blind spot"
- "safe on direct ideation but brittle on masked caregiver-collapse language"

This keeps the benchmark aligned with its purpose: a caregiver AI-centered audit
of strengths, weaknesses, and deployment-relevant failure mechanics.
