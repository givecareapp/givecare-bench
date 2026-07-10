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

## Defensible differentiation

No single ingredient below is unique. Multi-turn health and mental-health
benchmarks exist, caregiver-specific rubrics exist, and expert-authored scoring
exists. InvisibleBench's differentiated value is the conjunction: longitudinal
caregiver conversations, an explicit caregiver–recipient dyad, atomic
failure-mode verifiers, and a machine-enforced rule that withholds quantitative
Safety claims until each verifier clears independent calibration.

### 1. Longitudinal pressure inside caregiving

InvisibleBench evaluates **conversations**, not isolated responses. Safety
violations often accumulate across turns: a model that hedges on turn 1 may
quietly confirm a dangerous plan by turn 3. Relational quality also requires a
conversation arc to be visible.

Multi-turn evaluation itself is not the moat. [HealthBench](https://arxiv.org/abs/2505.08775),
[MindEval](https://arxiv.org/abs/2511.18491), and
[MHSafeEval](https://arxiv.org/abs/2604.17730) all evaluate multi-turn health or
mental-health interactions. InvisibleBench applies longitudinal pressure to a
different unit of analysis: the caregiver, the care recipient, and their
relationship, with fixed scenario provenance and per-check evidence retained
for every verdict.

### 2. The dyad inside a three-party interaction

Caregiving is structurally triadic: the caregiver, the care recipient, and the relationship between them. InvisibleBench models this explicitly. A recipient-harm act is categorised under Autonomy (Safety); an erasure of the caregiver–recipient bond is categorised under Relational (Care). A model that appropriately supports the caregiver while subtly undermining their relationship with the recipient fails a distinct check. Adjacent work recognizes care networks and recipient agency; InvisibleBench's narrower contribution is making the dyad an explicit, independently scored object throughout a conversational model evaluation.

### 3. Machine-enforced calibration gate

InvisibleBench's hard-fail layer is built as a **fail-closed, calibration-gated** gate: a Safety gate FAIL becomes a public claim *only* when its check is `claim_ready` (verifier cleared independent human-labeled natural-case calibration), and `qa_leaderboard.py` blocks publication of any hard-fail reason from a check that is not. The mechanism is the differentiator; the claims are gated behind it. (As of 2026-07-10, **0 checks are `claim_ready`** — the gate exists and is empty, with development evidence disclosed but no public hard-fail claim yet.)

The defensible present-tense claim is about the mechanism, not model quality:
uncalibrated checks cannot enter the public Safety surface. The gate is
currently empty. Independent human calibration is the work required to turn
that methodological safeguard into comparative quantitative claims.

### Nearest caregiver-specific comparator: RubRIX

[RubRIX](https://aclanthology.org/2026.findings-acl.1774/) is the closest
caregiver-specific comparator. It evaluates six models on more than 20,000
Reddit and ALZConnected caregiver queries across five clinician-validated risk
dimensions, then uses evaluator feedback to revise each initial response twice.
That scale and real-query grounding are strengths. Its unit of evaluation is a
response and its rubric-guided revisions, rather than an evolving
caregiver–model conversation. InvisibleBench trades that scale for controlled
longitudinal pressure, explicit caregiver–recipient dyad checks, and a
fail-closed per-check publication contract.

---

## Related work

InvisibleBench is a calibration-gated research benchmark for relational harms
in caregiver-support AI. It occupies a specific position: dyadic, multi-turn,
fail-closed evaluation with per-check evidence and publication maturity. It is
not yet a validated deployment gate because no check is `claim_ready`. Several
adjacent benchmarks evaluate related but distinct constructs.

| Benchmark | Overlap | Why it is not the same |
|---|---|---|
| **[RubRIX](https://aclanthology.org/2026.findings-acl.1774/)** | Closest caregiver-specific comparator. Uses more than 20,000 caregiver queries and five clinician-validated risk dimensions. | Scores an initial response and two rubric-guided revisions, not a longitudinal caregiver–model dialogue. Does not make the caregiver–recipient dyad or per-check publication maturity its output contract. |
| **[ADRD-Bench](https://arxiv.org/abs/2602.11460)** | Caregiving-adjacent, disease-specific. Includes ADRD Caregiving QA with 149 caregiving questions grounded in the Aging Brain Care program. | Knowledge/QA/clinical-reasoning assessment for Alzheimer's and dementia. Does not target relational safety failures, caregiver-to-recipient harm intent, artificial intimacy, scope deception, or boundary drift. |
| **[CareEval](https://emprise.cs.cornell.edu/care-eval/)** | Caregiver-specific physical-task reasoning with expert-grounded user-function, agency, communication, and safety criteria. | Evaluates plans for physical robot caregiving tasks rather than longitudinal caregiver-support conversations or artificial-intimacy boundaries. |
| **[MindEval](https://arxiv.org/abs/2511.18491)** | Multi-turn mental-health support benchmark with simulated patients and automatic LLM evaluation, built with licensed clinical psychologists. | Unit of analysis is therapy-like patient–clinician interaction and therapeutic competence. InvisibleBench's unit is caregiver–care-recipient–AI interaction. |
| **[MHSafeEval](https://arxiv.org/abs/2604.17730)** | Methodologically close: role-aware, adversarial, interaction-level, multi-turn mental-health safety evaluation with human-agreement analysis. | Counseling-safety discovery uses a role × harm taxonomy and simulated client trajectories. InvisibleBench fixes a caregiver corpus, scores the caregiver–recipient dyad, and exposes a per-check claim-readiness contract. |
| **[HealthBench](https://arxiv.org/abs/2505.08775)** | Large-scale health benchmark with 5,000 multi-turn conversations and physician-written rubrics. | Broad healthcare capability and safety evaluation. It does not specialize in family caregiving, caregiver burden, dyadic harm, artificial intimacy, or companion-compliance boundaries. |
| **MedHELM** | Broad medical LLM evaluation framework with clinician-validated taxonomy. | Evaluates medical tasks. Not a caregiver-support relational safety benchmark. |
| **Mental Health Crisis Benchmarks** | Crisis detection, safe response generation, human-vs-LLM evaluator agreement. | Crisis-focused, not caregiver-dyad-focused. Does not cover coordination burden, self-sacrifice reinforcement, recipient autonomy, artificial intimacy, or companion-regulatory scope. |

InvisibleBench's contribution is not another healthcare knowledge benchmark. It
combines a caregiver–care-recipient dyad harm ontology, atomic failure-mode
verifiers, Safety lines kept separate from Care distributions, and an evidence
contract in which every failure carries eligibility, severity, quoted evidence,
scorer route, and calibration status.

---

## Maturity axis

Not every dimension is ready to carry claims. Each is labelled:

- **`claim_ready`** — verifier meets the threshold (κ ≥ 0.65) vs an independent, human-labeled, natural-case calibration set; the verdict is a citable claim. **Currently none.**
- **`not_claim_ready`** — everything else. May carry disclosed development evidence (an authored AI-panel unit test on the 19 hard-fail checks, or layer-level `development_only`), reported directionally — but no public claim. (All 50 checks today.)
- **Named gaps** — e.g. Trauma-awareness: a dimension with a placeholder directory and no checks authored yet.

The comprehensive nine-dimension structure ships now. Calibration fills in over releases. The maturity label on each check prevents premature claim-making without hiding the gap — a reader can see exactly which cells are ready and which are not.

---

## Deliberate out-of-scope

**Usefulness** — whether advice was accurate, complete, or well-resourced — is someone else's lane. ADRD-Bench, medical QA benchmarks, and retrieval-augmented evaluation suites cover it well. InvisibleBench does not measure it, score it, or weight it. Adding usefulness checks would make the taxonomy non-MECE and dilute the relationship-risk signal the benchmark is designed to isolate.

This boundary is enforced in code: `build_scorecard` output carries `notes.out_of_scope: ["usefulness"]`, and the test suite asserts that no composite across safety and usefulness dimensions appears anywhere in the output.
