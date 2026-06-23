# What InvisibleBench Owns

Diátaxis: explanation

---

## The thesis

Usefulness scores cannot see harm. InvisibleBench measures what they miss: the safety violations and relational failures that appear exactly when a caregiver-AI system seems to be working fine.

A model that answers fluently, retrieves benefits accurately, and avoids hallucinated facts can still miss a passive-ideation cue, exceed its clinical authority, or erase the caregiver's relationship with the person they care for. None of that shows up in a usefulness rubric. All of it shows up here.

---

## The Safety + Care model

InvisibleBench uses two orthogonal axes — documented fully in [docs/ontology.md](ontology.md), not duplicated here.

**Safety** measures falsifiable prohibitions: hard lines the AI must not cross, reported as violation **rates** (claims, calibration-gated). Four lines — Crisis, Scope, Identity, Autonomy — partition the caregiver-AI failure surface by *which hard line was crossed*.

**Care** measures relational quality: how the AI shows up for the caregiver, reported as pass-rate **distributions** (directional, not averaged). Five qualities — Belonging, Attunement, Trauma-awareness, Relational, Advocacy — partition the caregiver's experience by *which aspect of that experience was honoured or failed*.

These two layers are reported separately, always. There is no composite score, no overall rank, no cross-layer merge. The design forces audit, not stack ranking.

---

## Three moats

No competing benchmark holds more than a gesture at any of these.

### 1. Multi-turn / longitudinal

InvisibleBench evaluates **conversations**, not posts or single exchanges. Safety violations often accumulate across turns: a model that hedges on turn 1 may quietly confirm a dangerous plan by turn 3. Relational quality requires a conversation arc to be visible at all. Every other published benchmark in this lane — RubRIX (arXiv 2601.13235, ACL 2026), ADRD-Bench (arXiv 2602.11460), CareEval (HRI 2026) — evaluates a single turn or a single post. Multi-turn is not a feature choice; it is a prerequisite for the measurement to be valid.

### 2. Three-party dyad

Caregiving is structurally triadic: the caregiver, the care recipient, and the relationship between them. InvisibleBench models this explicitly. A recipient-harm act is categorised under Autonomy (Safety); an erasure of the caregiver–recipient bond is categorised under Relational (Care). A model that appropriately supports the caregiver while subtly undermining their relationship with the recipient fails a distinct check. No competing benchmark encodes a three-party structure. A 2024 PMC systematic review identifies the dyad as the field's unaddressed gap; InvisibleBench addresses it directly.

### 3. Human-κ-calibrated safety gate with blocking FAIL

InvisibleBench's hard-fail layer is calibrated against human annotation (κ=1.0 on the 60-trace resolved gold set; 564 human-annotated cards at v3.1, κ by check in docs/verifier-validation.md). A gate-bucket FAIL is a **public claim** — it blocks publication if it lacks calibration evidence. The benchmark refuses to publish a hard-fail reason from an uncalibrated check.

Competing work uses LLM judges (RubRIX: GPT-5-nano, 88.67% raw agreement, no holdout; no κ reported) or clinician review without a blocking gate. Adjacent medical benchmarks compute reliability only on screening instruments, not on safety verdicts. No competitor has a mechanism that prevents an uncalibrated check from driving a published claim.

### Why RubRIX lacks all three moats

RubRIX is the closest competitor (Goel et al., OnCARE Lab, UIUC). It evaluates 20K real Reddit and ALZConnected posts with 29 binary questions across 5 risk dimensions using a Tronto ethics-of-care framework. The methodology is solid and the scale is impressive. It lacks: multi-turn structure (it evaluates posts, not conversations), a three-party dyad encoding (it models user+AI, not caregiver+recipient+relationship), and a calibrated hard-fail gate (risk flags are remediable, not blocking; no κ is reported). RubRIX submitted to arXiv in January 2026, approximately two months after InvisibleBench's original paper (November 2025). InvisibleBench has both temporal priority and a more advanced current instrument.

---

## Maturity axis

Not every dimension is ready to carry claims. Each is labelled:

- **Calibrated** — human-κ validated; per-mode gold sets; verdict is a citable claim. (Example: Crisis A1, A8; Identity F3.)
- **Provisional** — human-reviewed judge prompts with card-level evidence but no formal κ run; reported directionally, labeled. (Example: Scope, most Care qualities.)
- **To-author** — named gap in the taxonomy; placeholder directory exists; no checks authored yet. (Example: Trauma-awareness, Autonomy.)

The comprehensive nine-dimension structure ships now. Calibration fills in over releases. The maturity label on each check prevents premature claim-making without hiding the gap — a reader can see exactly which cells are ready and which are not.

---

## Deliberate out-of-scope

**Usefulness** — whether advice was accurate, complete, or well-resourced — is someone else's lane. ADRD-Bench, medical QA benchmarks, and retrieval-augmented evaluation suites cover it well. InvisibleBench does not measure it, score it, or weight it. Adding usefulness checks would make the taxonomy non-MECE and dilute the signal the three moats are designed to isolate.

This boundary is enforced in code: `build_scorecard` output carries `notes.out_of_scope: ["usefulness"]`, and the test suite asserts that no composite across safety and usefulness dimensions appears anywhere in the output.
