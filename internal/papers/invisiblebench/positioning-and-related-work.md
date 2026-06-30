# Positioning and Related Work

*Draft — paper section, not a final doc. Methods + results depends on the v1 Safety/Care build (Tasks #47–#55); leave a stub. Last updated: 2026-06-23.*

---

## 1  Thesis

A caregiver-AI response can be helpful, warm, and actionable while still being unsafe, over-scoped, dependency-building, or missing an escalation. InvisibleBench measures what usefulness scores cannot see.

---

## 2  One-Line Positioning

> RubRIX measures **caregiver-response risk** (per post, single turn, no gate).
> ADRD-Bench measures **dementia-care knowledge** (QA, single turn, no dyad).
> CareEval measures **robot caregiving action choices** (physical ADL, different lane).
> Older-adult AI feasibility studies measure **promise and adoption intent**.
>
> InvisibleBench measures whether a **caregiver-support AI stays safe, bounded, and honest across a caregiving relationship** — protecting the care recipient and the relationship itself, not just answering the caregiver.

---

## 3  Related Work

### 3.1  Background: caregivers as a distinct AI-safety population

Informal family caregivers number roughly 53 million in the United States (AARP/NAC 2020). AI health-information use in this population is accelerating rapidly: KFF (2025) found 29% of US adults use AI for health information, up from 17% in 2024, and 44% cannot distinguish accurate from inaccurate AI-generated health content. A subsequent Pew survey (June 2026) found 49% of US adults use chatbots, with 20% seeking medical guidance and 10% seeking emotional support. Family caregivers are concentrated in both of those high-stakes use cases.

The caregiver context carries safety properties that are absent from general health-information seeking. First, the caregiver acts as an intermediary — they translate AI output into decisions that affect a third party (the care recipient) who did not consent to and cannot correct the AI's influence. Second, the relationship itself is the therapeutic substrate; harms to the dyad are harms to the caregiver's capacity to care. Third, caregiver stress creates vulnerability to premature closure, false reassurance, and unhealthy reliance on the AI as a substitute for professional or community support.

Prior work has addressed adjacent problems. We situate InvisibleBench within that landscape and identify the gaps it fills.

### 3.2  RubRIX

RubRIX [CITE: Goel et al., arXiv 2601.13235, ACL Findings 2026] is the closest prior work. It defines five risk dimensions for evaluating AI responses to dementia caregiver posts: **Inattention** (ignoring emotional or informational needs), **Bias & Stigma** (othering or stigmatizing language), **Information Inaccuracy** (factual errors or harmful advice), **Uncritical Affirmation** (validating harmful caregiver behavior or plans), and **Epistemic Arrogance** (failure to defer appropriately to professional expertise). RubRIX applies these 29 binary items to AI-generated responses to 20,000 real Reddit and ALZConnected posts, using GPT-nano as a judge within a Tronto ethics-of-care theoretical frame.

RubRIX's contributions are genuine: it grounds risk assessment in a real-world post corpus, provides a multidimensional risk vocabulary, and roots the framework in established care ethics. It did not cite InvisibleBench (see §5, Priority).

Three structural gaps separate RubRIX from InvisibleBench:

1. **Single-turn, not longitudinal.** RubRIX evaluates one post and one AI response. Caregiving relationships unfold across sessions, across escalating stress, and across a trust arc that cannot be observed in a single turn. Dependency, false continuity, and relationship erosion are invisible in single-turn evaluation by design.

2. **Two-party, not triadic.** RubRIX evaluates whether the AI serves the caregiver (the poster). The care recipient does not appear as a party whose interests the AI must protect. InvisibleBench's **Protection** line (a Safety layer check) specifically tests whether the AI enables harm to, deception of, or autonomy override of the recipient — a failure mode that a two-party framework cannot score.

3. **Risk flags, not a hard-fail gate.** RubRIX's five dimensions produce risk flags — all are treated as remediable qualities to be improved. InvisibleBench's **Safety** layer produces a blocking gate: violation rates on Crisis, Scope, Identity, and Protection checks can fail a result closed, preventing publication. The gate is calibrated against a 60-trace human-adjudicated gold set (κ = 1.0 on the resolved set). RubRIX reports 88.67% human-judge agreement on its binary items but does not report inter-rater Cohen's κ or hold out a calibration set.

Despite its narrower scope, RubRIX's five risk dimensions map directly onto InvisibleBench's Safety layer (see §4, Crosswalk). InvisibleBench extends the RubRIX vocabulary into multi-turn evaluation, adds the dyadic third party, and adds a blocking calibration gate. It also adds a second layer — **Care** — that RubRIX's risk framing does not attempt.

### 3.3  ADRD-Bench

ADRD-Bench [CITE: arXiv 2602.11460] evaluates AI systems' factual and clinical knowledge about Alzheimer's disease and related dementias, using a single-turn QA format. It is complementary to InvisibleBench, not competing: ADRD-Bench tests what the AI knows; InvisibleBench tests how the AI behaves in a caregiver relationship. A model can score perfectly on ADRD-Bench (accurate knowledge) and still fail InvisibleBench by missing a crisis signal, making a false continuity claim, or infodumping accurate knowledge at a caregiver in crisis. ADRD-Bench has no multi-turn design, no dyad, and no safety gate.

### 3.4  CareEval

CareEval [CITE: HRI 2026] evaluates the action-level safety and appropriateness of physical robot caregiving decisions (activities of daily living: bathing, medication, mobility assistance). It operates in an entirely different lane — physical robot action selection rather than AI text communication — with a different risk model (physical harm from incorrect manipulation versus relational or informational harm from AI guidance). We cite it as evidence of the field's breadth; it shares no methodology or claims with InvisibleBench.

### 3.5  OnCARE Lab / UIUC (Goel et al.)

The OnCARE Lab (UIUC, Goel et al.) is the most active research group in the adjacent space. In a six-month window they published both RubRIX and "Inform, Coach, Relate, Listen" [CITE: arXiv 2605.29473], a communication-function taxonomy for AI caregiver responses. Their work establishes a growing research community around caregiving AI evaluation. A PMC systematic review contemporaneous with this submission identifies multi-turn evaluation and dyadic structure as the field's two principal unaddressed gaps — the two properties InvisibleBench has held since its November 2025 publication.

The strategic risk is clear: OnCARE is prolific and in exactly the same lane. The present paper plants the calibrated-gate + dyad + longitudinal flag in the literature before that group extends there.

### 3.6  Older-adult AI feasibility studies

A body of HCI and gerontology literature evaluates AI for older adults and caregivers primarily through feasibility, usability, and adoption lenses — measuring whether caregivers find AI useful, trustworthy, or acceptable. These studies provide the motivating evidence base (caregiver use of AI is real, accelerating, and consequential) but do not provide behavioral safety measurement. They measure promise; InvisibleBench measures whether that promise is kept.

---

## 4  Differentiation Table

| Dimension | **InvisibleBench** | **RubRIX** | **ADRD-Bench** | **CareEval** |
|---|---|---|---|---|
| **Unit of evaluation** | Multi-turn conversation (session + relationship arc) | Single post + AI response | Single-turn QA | Robot action sequence |
| **Party structure** | 3-party: caregiver + care recipient + relationship | 2-party: caregiver + AI | 1-party: AI knowledge | Physical care dyad (ADL) |
| **Calibration (κ?)** | Yes — safety gate κ = 1.0 (resolved gold, 60 traces); Tier-1 κ on 5 individual checks (range 0.747–0.795); ordinal-κ for Care layer in progress | 88.67% agreement; no κ reported; no holdout | Not reported | Not reported |
| **Hard-fail gate?** | Yes — blocking, fail-closed; QA gate prevents publication if coverage or gate thresholds not met | No — risk flags, all remediable | No | No |
| **Leaderboard?** | Yes — 11 models × 63 scenarios, public, updated with each publish run | No | No | No |
| **Output type** | Safety violation rates (claims) + Care quality distributions (directional); no composite score | 5-dimension risk profile; binary risk flags | Accuracy / knowledge score | Action-level safety score |

---

## 5  The Three Moats

### 5.1  Multi-turn / longitudinal evaluation

All three comparator benchmarks evaluate a single interaction: one Reddit post, one QA question, one robot action. InvisibleBench constructs **63 published scenarios** (64 on disk) as **multi-turn sessions**: a caregiver persona, a care context, and a sequence of turns that can span acute crisis, follow-up, emotional check-in, and relationship maintenance.

The multi-turn structure is what makes certain failure modes visible. False continuity claims ("I'll be here when you come back" — identity.memory-claim, κ = 0.795) require turn 2 to observe. Dependency-building requires observing whether the AI repeatedly anchors the caregiver back to itself rather than to human support. Crisis signal negation (crisis.false-reassurance, κ = 0.747) is most dangerous when the caregiver tested the AI's attention on turn 1 and escalates on turn 2. A 2025-generation model family showed up to 22.3% body-presence language rates across the legacy fleet; no single-turn study has the structure to detect what that pattern does over a sustained relationship.

No comparator benchmark has a multi-turn design. A PMC systematic review on caregiving AI evaluation explicitly names this as the field's primary structural gap.

### 5.2  The three-party caregiver–recipient dyad

When a caregiver asks an AI for advice, there are three parties in the room: the caregiver, the care recipient, and the relationship between them. InvisibleBench is designed around that structure. The **Protection** line in the Safety layer tests specifically whether the AI enables harm to, deception of, or autonomy override of the care recipient — the person who did not choose to involve an AI in their care and cannot correct the AI's influence.

The dyadic structure is also why InvisibleBench detected harm-fear normalization (crisis.harm-intent, 22.5% in the legacy sweep): when a caregiver says "I'm afraid I'll hurt her because I'm so fried," the danger signal lives in the relationship clause ("hurt her"), not in any keyword that single-turn safety classifiers check for. General-purpose safety training catches "I want to hurt myself." It systematically misses "I'm afraid I'll hurt someone else" because the third party is invisible.

The **Relational** quality in the Care layer similarly requires a three-party structure to score: does the response erode or strengthen the caregiver–recipient bond? A two-party evaluation cannot ask that question.

No comparator benchmark models the care recipient as a party with interests the AI must protect. RubRIX's Uncritical Affirmation check approaches this by flagging validation of harmful caregiver plans — but it evaluates the AI's output to the caregiver, not the downstream effect on the recipient.

### 5.3  Human-κ-calibrated safety gate (fail-closed, blocking)

InvisibleBench's Safety layer has a hard-fail gate: if a result is below the coverage floor or carries gate-bucket UNCLEAR verdicts, it cannot be published. The gate is calibrated — its verdicts agree with human-adjudicated gold at κ = 1.0 on a 60-trace resolved gold set (with caveats disclosed: pre-adjudication human–human agreement was weakest on the compliance layer; the gold comes from prior-generation models). Five individual checks have separate Tier-1 κ (range 0.747–0.795) against unresolved human labels.

This is structurally different from what comparators offer:

- RubRIX uses GPT-nano as a judge with 88.67% binary agreement — no κ, no holdout, no blocking semantics.
- ADRD-Bench and CareEval do not report calibration against human labelers in the sense of a failure-verdict gate.

The gate matters because a Safety finding without calibration is not a safety claim. It is a model output. InvisibleBench distinguishes the two and encodes that distinction in the publication boundary: the QA gate (`qa_leaderboard.py`) blocks publication if calibration requirements are not met. The Care layer does not yet clear the calibration threshold for claims (ordinal-κ validation in progress); it is reported as directional. The architecture keeps the claim/directional distinction machine-enforced, not a prose caveat.

---

## 6  RubRIX Crosswalk: InvisibleBench as a Superset

RubRIX's five risk dimensions map onto InvisibleBench's Safety and Care layers as follows. InvisibleBench extends or supersedes each.

| RubRIX dimension | InvisibleBench coverage | Extension |
|---|---|---|
| **Inattention** — ignoring the caregiver's emotional or informational needs | Care → **Attunement** (register/recognition match), **Belonging** (othering ↔ affirming) | Multi-turn; ordinal gradient, not binary; tests the relational arc, not a single post |
| **Bias & Stigma** — othering, stigmatizing language about caregivers or recipients | Care → **Belonging** (othering ↔ affirming) | Explicitly graduated (not a binary flag); includes recipient-directed as well as caregiver-directed stigma |
| **Information Inaccuracy** — factual errors, harmful advice | Safety → **Scope** (no diagnosis, no prescribing, no professional directives) | Scope adds a blocking gate; IB-B/D checks distinguish over-advice from inaccuracy |
| **Uncritical Affirmation** — validating harmful caregiver plans or feelings without challenge | Safety → **Protection** (don't enable harm to recipient); Care → **Trauma-awareness** | Protection adds the recipient's interests; Trauma-awareness tests whether the AI interrupts guilt and harm loops |
| **Epistemic Arrogance** — failure to defer to professional expertise | Safety → **Scope** (stay in your lane: no credentials, no directives) | Scope is a hard-fail gate; repeated professional-claim patterns block publication |

InvisibleBench's Care layer adds four qualities that RubRIX has no equivalent for: **Belonging** as a scored gradient (not a binary risk flag), **Attunement** across an emotional arc, **Trauma-awareness** as an explicit scoring dimension, and **Relational** quality (does the response erode or strengthen the dyad). These are not risk flags; they are positive dimensions of what good caregiving-AI support looks like, scored as distributions.

---

## 7  Priority Claim

InvisibleBench's original public release — benchmark instrument, scenario set, and leaderboard — was published in **November 2025**. RubRIX was submitted to ACL ARR in **January 2026**, approximately two months later, and published as ACL Findings 2026. RubRIX did not cite InvisibleBench. This is a citation-hygiene miss, not a prioritization ambiguity: InvisibleBench was in the literature at the time of RubRIX's submission.

InvisibleBench therefore holds temporal priority on the multi-turn + dyadic + calibrated-gate approach to caregiving-AI safety evaluation. The advances since the November 2025 release reinforce that position:

- **Safety/Care ontology (2026-06-23).** The original benchmark used a letter-coded A/B/C/D/F/G taxonomy. The current instrument replaces it with a principled two-layer ontology — Safety (four prohibition lines: Crisis, Scope, Identity, Protection) and Care (four caregiver-centered qualities: Belonging, Attunement, Trauma-awareness, Relational) — with the Dyad dissolved into both layers rather than treated as a separate dimension. No composite score; the two layers are reported side by side.
- **Calibration expansion.** The November 2025 instrument had a 60-trace gate calibration. V3.1 (2026-04-30) expanded to 53 checks across 564 human-annotated cards, rewrote four verifier prompts after adjudication, and added Tier-1 κ on individual Safety checks.
- **Leaderboard.** Phase 2 covers 11 models × 63 scenarios with cluster-robust standard errors, 95% CIs, and `rank_upper_bound` (paired tests on per-scenario hard-fail; clusters = contrast families). The November 2025 release had no leaderboard.
- **The longitudinal finding.** The Phase 2 data establishes, to our knowledge, the first human-calibrated longitudinal record of relational safety improving across a model generation: the 2025 fleet's failure modes (artificial intimacy, false continuity, identity misrepresentation) are largely absent in the 2026 roster on the same calibrated checks.

---

## 8  What This Paper Adds Over the November 2025 Version (stub)

*[Full section deferred — depends on v1 Safety/Care build. Outline:]*

1. **The Safety/Care ontology** — principled two-layer structure with claim/directional separation, replacing the letter-coded composite.
2. **Calibration provenance** — Tier-1 κ on 5 Safety checks; disclosed limits on the compliance gate gold set; Care layer quality and epistemic status.
3. **The longitudinal finding** — first human-calibrated cross-generation comparison, showing which 2025 failure modes have resolved and which 2026 failure modes have emerged.
4. **The dyad, operationalized** — Protection (Safety) and Relational (Care) dissolve the "Dyad" into a tractable dual-layer structure instead of a stand-alone dimension.
5. **Leaderboard under statistical discipline** — cluster-robust SEs, CIs, `rank_upper_bound`; the point is jagged profiles and blind spots, not a stack rank.

*[Stub: methods and results section — to be written after the v1 Safety/Care instrument build is complete (Tasks #47–#55). Will cover: reclassification of 53 checks into the new ontology; violation-rate scoring for Safety; Belonging calibration (the v1 distinctiveness proof); Phase 2 results under the new schema; comparison to v1 rates.]*

---

## References (placeholder — to be formatted per venue style)

- Goel et al. (2026). "RubRIX: A Rubric-Based Framework for Evaluating AI Responses to Dementia Caregiver Social Media Posts." *Findings of ACL 2026*. arXiv:2601.13235.
- Goel et al. (2026). "Inform, Coach, Relate, Listen: Communication Functions in AI Caregiver Responses." arXiv:2605.29473.
- [ADRD-Bench authors] (2026). ADRD-Bench: Benchmarking AI on Alzheimer's Disease and Related Dementia Knowledge. arXiv:2602.11460.
- [CareEval authors] (2026). CareEval: Evaluating Robotic Caregiving Action Safety. *HRI 2026*.
- AARP/NAC (2020). Caregiving in the United States 2020. AARP Public Policy Institute.
- KFF (2025). AI and Health Information Survey. Kaiser Family Foundation.
- Pew Research Center (June 2026). Americans and AI Chatbots for Health Information.
- [PMC systematic review — multi-turn/dyad gap finding. Full citation TBD.]
- Tronto, J. (1993). Moral Boundaries: A Political Argument for an Ethic of Care. Routledge.
