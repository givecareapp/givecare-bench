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

InvisibleBench's hard-fail layer is built as a **fail-closed, calibration-gated** gate: a Safety gate FAIL becomes a public claim *only* when its check is `claim_ready` (verifier cleared independent human-labeled natural-case calibration), and `qa_leaderboard.py` blocks publication of any hard-fail reason from a check that is not. The mechanism is the moat; the claims are gated behind it. (As of 2026-06-30, **0 checks are `claim_ready`** — the gate exists and is empty, with development evidence disclosed but no public hard-fail claim yet.)

Competing work uses LLM judges (RubRIX: GPT-5-nano, 88.67% raw agreement, no holdout; no κ reported) or clinician review without a blocking gate. Adjacent medical benchmarks compute reliability only on screening instruments, not on safety verdicts. No competitor has a mechanism that prevents an uncalibrated check from driving a published claim.

### Why RubRIX lacks all three moats

RubRIX is the closest competitor (Goel et al., OnCARE Lab, UIUC). It evaluates 20K real Reddit and ALZConnected posts with 29 binary questions across 5 risk dimensions using a Tronto ethics-of-care framework. The methodology is solid and the scale is impressive. It lacks: multi-turn structure (it evaluates posts, not conversations), a three-party dyad encoding (it models user+AI, not caregiver+recipient+relationship), and a calibrated hard-fail gate (risk flags are remediable, not blocking; no κ is reported). RubRIX submitted to arXiv in January 2026, approximately two months after InvisibleBench's original paper (November 2025). InvisibleBench has both temporal priority and a more advanced current instrument.

---

## Related work

InvisibleBench is a calibrated deployment gate for relational harms in caregiver-support AI. It occupies a specific position: dyadic, multi-turn, fail-closed, verifier-calibrated safety evaluation for caregiver-support AI. Several adjacent benchmarks evaluate related but distinct constructs.

| Benchmark | Overlap | Why it is not the same |
|---|---|---|
| **RubRIX** | Closest caregiver-specific comparator. Explicitly about caregiver-AI interactions, uses caregiver-authored queries, defines caregiver-specific risks (inattention, bias/stigma, uncritical affirmation, epistemic arrogance). | Response-level risk evaluation and mitigation over Reddit/ALZConnected caregiver queries. Not a multi-turn deployment gate with fail-closed safety checks, per-mode verifier calibration, or identity-boundary drift detection. |
| **ADRD-Bench** | Caregiving-adjacent, disease-specific. Includes ADRD Caregiving QA with 149 caregiving questions grounded in the Aging Brain Care program. | Knowledge/QA/clinical-reasoning assessment for Alzheimer's and dementia. Does not target relational safety failures, caregiver-to-recipient harm intent, artificial intimacy, scope deception, or boundary drift. |
| **MindEval** | Multi-turn mental-health support benchmark with simulated patients and automatic LLM evaluation, built with licensed clinical psychologists. | Unit of analysis is therapy-like patient-clinician interaction and therapeutic competence. InvisibleBench's unit is caregiver-care-recipient-AI interaction, where the model can harm the caregiver, the recipient, or the relationship between them. |
| **MHSafeEval** | Methodologically close: role-aware, interaction-level, multi-turn mental-health safety evaluation. Explicitly argues static/single-turn benchmarks miss cumulative harms. | Counseling-safety focused with a role taxonomy. InvisibleBench's distinctive axes are caregiver dyad safety, practical care coordination, companion-boundary regulation, and deployment-gate scoring. |
| **HealthBench** | Large-scale health benchmark with 5,000 multi-turn conversations and physician-written rubrics. | Broad healthcare capability/safety evaluation. Does not specialize in family caregiving, caregiver burden, dyadic harm, artificial intimacy, or companion compliance boundaries. |
| **MedHELM** | Broad medical LLM evaluation framework with clinician-validated taxonomy. | Evaluates medical tasks. Not a caregiver-support relational safety benchmark. |
| **Mental Health Crisis Benchmarks** | Crisis detection, safe response generation, human-vs-LLM evaluator agreement. | Crisis-focused, not caregiver-dyad-focused. Does not cover coordination burden, self-sacrifice reinforcement, recipient autonomy, artificial intimacy, or companion-regulatory scope. |

InvisibleBench's contribution is not another healthcare benchmark. It contributes a new harm ontology (caregiver–care-recipient dyadic safety), a new decomposition (subjective caregiver pain points converted into atomic verifier checks), a new scoring posture (per-line violation rates before quality distributions), and a new evidence contract (every failure carries eligibility, severity, quoted evidence, scorer route, and calibration status).

---

## Maturity axis

Not every dimension is ready to carry claims. Each is labelled:

- **`claim_ready`** — verifier meets the threshold (κ ≥ 0.65) vs an independent, human-labeled, natural-case calibration set; the verdict is a citable claim. **Currently none.**
- **`not_claim_ready`** — everything else. May carry disclosed development evidence (an authored AI-panel unit test on the 19 hard-fail checks, or layer-level `development_only`), reported directionally — but no public claim. (All 50 checks today.)
- **Named gaps** — e.g. Trauma-awareness: a dimension with a placeholder directory and no checks authored yet.

The comprehensive nine-dimension structure ships now. Calibration fills in over releases. The maturity label on each check prevents premature claim-making without hiding the gap — a reader can see exactly which cells are ready and which are not.

---

## Deliberate out-of-scope

**Usefulness** — whether advice was accurate, complete, or well-resourced — is someone else's lane. ADRD-Bench, medical QA benchmarks, and retrieval-augmented evaluation suites cover it well. InvisibleBench does not measure it, score it, or weight it. Adding usefulness checks would make the taxonomy non-MECE and dilute the signal the three moats are designed to isolate.

This boundary is enforced in code: `build_scorecard` output carries `notes.out_of_scope: ["usefulness"]`, and the test suite asserts that no composite across safety and usefulness dimensions appears anywhere in the output.
