# Benchmark Publishing Audit

InvisibleBench publishes benchmark work in two linked phases:

1. **Code documentation** — the benchmark contract, scorer mechanics, verifier
   routing, calibration status, and release commands are documented in the repo
   before the results are treated as public claims.
2. **Result narrative** — the generated benchmark outputs are QA-gated, reduced
   into a web payload, and presented as caregiver-centered failure-mode analysis.
   No result artifact is checked in until `scripts/qa_leaderboard.py --strict`
   passes against the current benchmark contract.

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
- `scripts/run_scan.py`, `delivery/combine_scans.py`,
  `scripts/generate_leaderboard.py`, `scripts/qa_leaderboard.py`, and
  `delivery/sync_web_bench.py` form the fail-closed path from complete,
  common-profile scans to the public scorecard. `delivery/combine_scans.py`
  requires exact scenario-set parity, one publish profile, one judge, complete
  cost accounting, and no duplicate model/scenario rows. It accepts only scan
  plan v2 artifacts with complete source-run and transcript hashes, identical
  full check-definition snapshots, and one comparability fingerprint.
- Transcript `run_manifest.json` v2 pins the exact scenario roster, corpus and
  check definitions, harness and mode, system-prompt/tool policy, generation
  parameters, retries, and source revision. `scan_plan.json` v2 then binds the
  exact selected transcript bytes to that run policy.
- `delivery/build_public_transcript_release.py` independently projects raw run
  artifacts into allowlisted, provenance-complete public transcript bundles.
  It verifies the exact v4 inventory and shared corpus hash and excludes local
  paths and provider metadata.
- `delivery/build_public_score_release.py` projects the strict-QA-ready merged
  scan into model-specific per-check evidence bundles. It preserves check
  verdicts, repetitions, prompt hashes, rationale codes, and transcript quotes,
  while excluding host paths, provider metadata, and internal composite fields.
- Live judge scans write a durable row checkpoint and cumulative cost state
  after every completed transcript. `--resume <incomplete-scan-dir>` verifies
  the original source/options signature and skips completed rows, so a hard
  ceiling or process failure does not turn paid work into an unusable partial.

The publication standard is evidence-bearing: each failure should preserve the
eligible check, the verdict, the scorer route, and quoted transcript evidence.
The code docs should make it possible to audit how a public claim was produced
without relying on a single opaque LLM judge.

## Phase 2: Results And Scoring Narrative

The result phase starts from a current-version scored scan. The checked-in v4
scorecard is a historical research snapshot: its source merge is v1 and cannot
pass the current v2 provenance gate. A publication replacement must come from
newly complete v2 run and scan manifests; the gate does not infer missing
lineage from old artifacts.

- The current public framework is `safety-care/v1`; runtime versions and exact
  inventory come from their machine-readable sources.
- Strict QA requires complete scenario/check coverage, no blocking unresolved
  verdicts, a current benchmark version, exact observed prompt and full
  check-definition hashes, complete v2 merge provenance, and a matching
  manual-adjudication ledger when manual results exist.
- Safety-override suppression is represented as an ineligible
  `NOT_APPLICABLE` result, never as a missing check.
- Generated timestamps and validation diagnostics are read from
  `scan_metadata`, never copied into prose.
- The artifact also carries `scan_metadata.artifact_issue_policy`, which
  classifies eligible `NOT_APPLICABLE` as resolved coverage, literal `UNCLEAR`
  as a strict-QA blocker, and scorer parse/truncation counters as retry
  diagnostics whose final resolved verdict remains authoritative.
- `scan_metadata.check_coverage` reports, for every model/check pair, total,
  eligible, ineligible, PASS, FAIL, NOT_APPLICABLE, UNCLEAR, scorer-error, and
  retry-parse-error counts. QA recomputes it from the scan; it is metadata, not
  a score.

The web-bench payload is a lean projection of that artifact:

- Target: `../gc-web/apps/web-bench/public/bench/leaderboard.json`
- Payload shape (`safety-care/v1`): `schema`, `notes`, `scan_metadata`, and
  `models` — each model carrying `safety` (per-line violation rates + aggregate)
  and `care` (per-quality distributions). `delivery/sync_web_bench.py` validates
  the source and rejects non-public top-level keys before writing.
- Local projection drift is read-only health state: after generation,
  `bench health` reports whether `leaderboard_web.json` lags
  `leaderboard.json`; it does not sync or write the projection.
- No `findings` block: thematic failure clusters, contrast sets, and
  field-relative model signatures are NOT in the lean payload. They are deferred
  to a re-authored Safety/Care artifact-v2.
- The historical public audit bundles remain inspectable, but their older
  manifests do not satisfy the current scan-merge v2 provenance gate. New
  transcript and score bundles remain allowlisted and exclude host-specific
  paths.

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
