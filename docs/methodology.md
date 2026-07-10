# Methodology

> Diátaxis: explanation

InvisibleBench grounds its scoring dimensions in established clinical, regulatory, and social frameworks. This page explains what we measure, why, and which authorities inform each dimension. For the canonical taxonomy and maturity map, see [ontology.md](ontology.md). For scoring mechanics (rates, distributions, calibration gating), see [Scoring Rubric](scoring-rubric.md).

---

## The Safety/Care model

InvisibleBench v1 uses a **two-layer model** — not a gate-then-quality pipeline, not a single composite score.

```
SAFETY layer  →  VIOLATION RATES (falsifiable prohibitions)
CARE layer    →  DISTRIBUTIONS   (gradients, directional)
```

**Safety** answers: *Did it cross a hard line?* Four lines partition the safety failure surface — Crisis, Scope, Identity, Autonomy. Each line produces a conditional violation rate: the fraction of eligible scenarios with ≥1 failure on any check in that line. Lower rate = safer. Severity (S2–S5) annotates the gravity of each failure; it does not gate whether a scenario is counted in the rate.

**Care** answers: *How well did it show up for the caregiver?* Five qualities partition the relational surface — Belonging, Attunement, Trauma-awareness, Relational, Advocacy. Each quality produces a directional pass-rate distribution across eligible check evaluations. These are directional signals, not validated absolute claims, and they are never averaged across qualities.

**No composite.** The two layers are orthogonal — a model can have a low Crisis violation rate and a poor Belonging distribution, or vice versa. There is no formula that merges them into an `overall_score` or rank. The schema `safety-care/v1` enforces this: the artifact carries `notes.no_composite: true` and no ranking key.

---

## Framework grounding

The nine dimensions operationalize **GiveCare's Design Charter**, which synthesizes three recognized frameworks: SAMHSA trauma-informed care, Microsoft Inclusive Design, and the Othering & Belonging Institute (OBI) Targeted Universalism. InvisibleBench measures whether a deployed model upholds the same principles the product is designed to — grounding the benchmark in the same charter that governs `gc-sms`.

The per-dimension grounding table (dimension → framework → charter principle) is canonical in **[ontology.md § Framework grounding](ontology.md#framework-grounding)** and is not duplicated here. The subsections below explain what each framework contributes.

### SAMHSA — Trauma-Informed Care (2014)

Six principles: safety, trustworthiness, peer support, collaboration, empowerment, cultural sensitivity. These principles are the foundation ring for every dimension: Crisis and Autonomy operationalize *safety*; Scope and Identity operationalize *trustworthiness*; Relational maps to *peer support*; Trauma-awareness grounds directly in all six principles as a whole.

### Microsoft Inclusive Design

Inclusive Design contributes the cognitive and emotional states lens: evaluating whether the model meets the caregiver where they are rather than where it wants them to be. Attunement is the primary carrier of this principle.

### OBI Targeted Universalism (powell and Menendian, 2024)

Targeted Universalism sets a universal goal (reduce logistical burden for all caregivers) and demands awareness of the tailored barriers different groups face. It also contributes the RACI belonging framework:

| OBI Belonging Component | Definition | Dimension mapping |
|---|---|---|
| Recognition | "All are accorded visibility — seen, respected, and valued" | Care · Belonging |
| Agency | "The power to act and the potential to influence" | Safety · Autonomy; Care · Belonging |
| Connection | "A tether or tie to another person, community, group" | Care · Relational |
| Inclusion | "All social groups included in critical institutions" | Care · Belonging |

Advocacy maps to OBI's power-aware Targeted Universalism: a model that speaks for the institution when the caregiver is in conflict with the system fails this dimension regardless of how warm it sounds.

---

## Grounding layers

| Layer | Function | Primary sources |
|---|---|---|
| **Invisible risk** | Anthropomorphism, emotional entanglement, confabulation | NIST AI 600-1 §§2.2, 2.7; MS-2.5-004 |
| **Behavioral safety** | Crisis routing, scope honesty, not-therapy | NAMI AI Evaluation (2026, 5 criteria); 988 Lifeline Standards |
| **Patient voice** | What caregivers actually need from AI companions | NHC Patient Voice Report (Morrissey, 2026) |
| **Caregiver realism** | Actual caregiver conditions and infrastructure | NAC + AARP "Caregiving in the US 2025"; ACL/NFCSP; Eldercare Locator |
| **Regulatory floor** | Legal requirements by jurisdiction | WOPR Act (IL), CA SB 243, NV AB 406, NY Article 47, EU AI Act, and others |

---

## Calibration and claims

InvisibleBench makes **calibration-gated claims** under a binary claim model: only checks whose `calibration:` block carries status `claim_ready` feed published Safety rates. As of 2026-07-01, **0 of 50 checks are `claim_ready`, so the published Safety claim surface is empty.**

**Claim model (2026-06-30):**

| Status | Meaning | Current members |
|---|---|---|
| `claim_ready` | Verifier meets the agreement threshold (κ ≥ 0.65) vs an independent, human-labeled, natural-case calibration set | (none yet) |
| `not_claim_ready` | Everything else; may carry disclosed development evidence (`calibration.evidence`) but makes no public claim | all 50 checks |

The 19 hard-fail checks hold `authored_ai_unit_test` development evidence (AI reference-panel labels on authored cards — not validation) and the historical 60-trace layer-level result as `development_only` evidence — neither is a public claim. `scope.periodic-disclosure` was demoted out of the hard-fail/claim layer on 2026-07-01. See [verifier-validation.md](verifier-validation.md) for the full reading guide.

**What this means for public claims:**

- Safety violation rates are the *intended* public-claim surface (calibration-gated, per-line, conditional-denominator rates with cluster-robust 95% CIs and a Wilson boundary fallback) — but **the surface is currently empty (0 `claim_ready`)**, so no Safety rate is a public claim yet.
- Care distributions are directional signals, never claim-bearing: Belonging has inter-model κ=0.82 (development only); Attunement, Relational, and Advocacy are directional/authored; Trauma-awareness has no checks yet.
- There is no composite or ranking key to mis-cite.

**Current result status:**
No leaderboard is checked in. Publication begins with a fresh 4.0 transcript
run and current-contract scan; generated artifacts preserve expected and
observed per-check prompt hashes, and strict QA blocks any coverage, verdict,
version, or hash mismatch. The next live `--full` run targets 15 models × 63
scenarios. Its exact OpenRouter IDs and list prices were refreshed on
2026-07-10; `src/invisiblebench/models/config.py` is the roster source of truth.
The GPT-5 Mini verifier remains intentionally frozen pending separate
per-check re-validation, so a target-roster refresh cannot silently change the
measurement instrument.

---

## Runtime adjudication

The scoring system is a **hybrid per-check verifier** architecture — a deliberate departure from the monolithic LLM-as-judge paradigm.

1. Deterministic lexicon scorers catch bright-line failures fleet-wide — fast, reproducible, zero token cost.
2. LLM verifiers adjudicate semantic edge cases on eligible checks — using token escalation (4000 → 8000 → 16000) before failing closed.
3. Scan profiles separate cheap development feedback (`--profile dev`) from strict publication scoring (`--profile publish`).
4. Verifier behavior is audited against the resolved human gold set (60/60 on the prior layer-level gold) — recorded as development evidence, not a public claim (0 checks are `claim_ready`).
5. Strict leaderboard artifacts may include local manual adjudication of residual `UNCLEAR` verdicts, recorded with transcript paths and quoted evidence.
6. Each check produces an independent pass/fail verdict with evidence spans — not a holistic score.

**Fail-closed design:** LLM-verifier retry exhaustion fails closed (FAIL, after token escalation). Unexpected verifier crashes yield `UNCLEAR + adjudication_required` — never a fabricated FAIL. FAIL is a public claim requiring evidence; QA enforces `fail_without_evidence=0`.

See [Architecture — Verifier architecture](architecture.md#verifier-architecture) and [Taxonomy](taxonomy.md) for the implementation rationale.

---

## Positioning and related work

The positioning analysis, the three moats, and the related-work comparison (RubRIX, ADRD-Bench, MindEval, MHSafeEval, HealthBench, MedHELM, crisis benchmarks) live in **[what-invisiblebench-owns.md](what-invisiblebench-owns.md)** — not duplicated here.

---

## Baseline dimension coverage

These 10 baseline dimensions represent the minimum evaluation surface for a wellness/mental-health-adjacent caregiver benchmark.

| Baseline dimension | Layer / line-or-quality | Coverage | Status |
|---|---|---|---|
| Crisis recognition and routing | Safety · Crisis | crisis.passive-ideation through crisis.disengagement | **Covered** |
| Scope honesty | Safety · Scope | scope.diagnosis through scope.false-records + clinical-directive checks | **Covered** |
| Identity honesty / anti-dependency | Safety · Identity | identity.body-claim, identity.dependency, identity.memory-claim | **Covered** |
| Recipient autonomy protection | Safety · Autonomy | autonomy.override, autonomy.coercion, autonomy.threats, autonomy.closed-options | **Covered** |
| Caregiver recognition | Care · Belonging | belonging.self-diminishment, belonging.recognition-gap, belonging.othering, belonging.hero-framing, belonging.self-sacrifice | **Covered** |
| Emotional attunement | Care · Attunement | attunement.generic-warmth, attunement.advice-first, attunement.guilt-loop, attunement.infodump, others | **Covered** |
| Resource quality | Care · Relational / Advocacy | Named; verification against live resources remains out of scope | **Partial** |
| Trauma-informed language | Care · Trauma-awareness | Named gap — 0 authored checks | **Gap** |
| Sensitive-disclosure minimization | — | Product design concern, not conversation scoring | Outside scope |
| Evidence discipline | — | Requires ground-truth infrastructure | Outside scope |

*Sources: NAMI AI Evaluation criteria (2026), NIST AI 600-1, NHC Patient Voice (2026), 988 Lifeline Standards.*

---

## Scope boundaries

!!! note "What InvisibleBench evaluates — and what it does not"

    InvisibleBench evaluates **conversations**, not apps or products.

    **The scripted-user ceiling.** Caregiver turns are deterministic scripts with rule-based branching—there is no reactive user simulator. Multi-session scripts preserve session number, elapsed time, and authored session context, while the raw harness still supplies prior turns in one model request history. They test scripted continuity under an explicit time gap, not product persistence or months-scale memory. Branch paths can differ by model, so exact comparisons require conditioning on the recorded `branch_id` or using fixed-path subsets. A calibrated user simulator or true persistence harness would be a new `benchmark_version`, never a quiet swap.

    **Privacy honesty.** If a model makes false privacy or capability claims *within* a conversation, the Scope/Identity lines catch it. Systematic product privacy evaluation requires a different methodology.

    **Sensitive-disclosure minimization.** What the app *solicits* is a product-design concern, not a property of any single conversation turn.

    **Evidence discipline.** Testing whether cited resources are factually accurate requires ground-truth infrastructure that operates at a different layer than conversation evaluation.

    **Youth safeguards.** InvisibleBench targets adult family caregivers. Youth populations have distinct risk profiles requiring purpose-built scenarios and clinical review.

    **Post-caregiving bereavement.** InvisibleBench evaluates active caregiving relationships. Bereaved former caregivers have distinct needs — identity reconstruction, complicated grief — that are adjacent but not yet covered.

    **Care-recipient-initiated harm toward the caregiver.** crisis.harm-intent covers the caregiver fearing they will harm the care recipient. The inverse — the care recipient's aggression toward the caregiver (common in dementia at >20% prevalence) — is partially covered by crisis.recipient-aggression but requires fuller purpose-built scenario coverage.

    **Proxy ethical decision-making.** End-of-life decisions and advance directive navigation touch both the Scope line (clinical positions) and Care qualities (moral distress). scope.forced-nutrition is the current single check; broader proxy ethics coverage is deferred.

---

## Out-of-scope frameworks

These frameworks are relevant to the broader AI mental health ecosystem but evaluate a different unit of analysis or population.

| Category | Source | What it provides | When to promote |
|---|---|---|---|
| App evaluation | APA App Evaluation Model | Hierarchical question set: background, access, privacy/security, evidence, usability, data integration | If InvisibleBench adds product-level privacy/security evaluation |
| App evaluation | MIND / MINDapps (105 questions) | Operationalized evaluation of mental health apps; public database | If InvisibleBench evaluates app-level features |
| App evaluation | FTC Mobile Health App Tool | Maps federal laws to health apps; data breach obligations | If InvisibleBench adds product-level privacy/security scenarios |
| Youth safeguards | Youth-Use Survey (2025) | 13.1% US youth used GenAI for MH advice; 65.5% monthly | If young caregiver scenarios are added |
| Youth safeguards | JAMA Chatbot Safety Study (2025) | Only 36% had age verification; 46.7% of companion bots had self-harm policies | If evaluating youth-facing features |
| Empirical calibration | 2025 Meta-Analysis | Chatbot interventions reduced distress modestly; no significant effect on psychological well-being | Calibrates expectations but does not change scoring |

---

## Caregiver context

!!! info "Why caregivers specifically"

    InvisibleBench targets family caregivers because they represent a large, underserved population operating in high-stakes conditions with limited support infrastructure.

**Prevalence.** 63 million US adults are unpaid caregivers (NAC + AARP, 2025), providing high-intensity care that disrupts employment, increases isolation, and generates sustained emotional stress.

**Co-occurring conditions.** Dementia caregivers experience depression at 16% prevalence and provide an estimated $413 billion in unpaid care annually (Alzheimer's Association, 2025). Chronic disease caregivers face elevated rates of anxiety and depression — Parkinson's (50% depression, 40% anxiety), lupus (54% moderate-to-severe anxiety), arthritis (depression 2–10× general population).

**The companion model.** Patient communities with rare and chronic diseases view AI "not as a doctor replacement, but as a scalable companion to bridge the gap between daily needs and clinical visits" — the 98% of time outside clinical care (NHC Patient Voice, 2026).

**Design implication.** The NHC report concludes: "Prioritize continuity, availability, and contextual safety over novelty." Turkle's artificial-intimacy thesis operationalizes this: AI should scaffold human presence, not simulate relationship.

**Market accountability gap.** No standardized third-party evaluation exists for AI safety in mental health and caregiving contexts. Companies self-report safety measures; there is no independent verification of crisis detection capabilities or accountability for longitudinal harms. InvisibleBench addresses this gap.

---

## Full references

### Regulatory

- **CA AB 3030.** AI disclosure required for health communications. [Text](https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202320240AB3030)
- **CA SB 243.** Companion chatbot safety safeguards; evidence-based suicidal ideation detection required. [Text](https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202520260SB243)
- **CO SB24-205.** Healthcare AI classified as high-risk. [Text](https://leg.colorado.gov/bills/sb24-205)
- **EU AI Act (2024/1689).** Regulation on artificial intelligence. Prohibited: manipulation exploiting vulnerabilities. [Text](https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng)
- **FDA General Wellness Framework.** Peer support and wellness guidance allowed; clinical treatment is not. [Guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/general-wellness-policy-low-risk-devices)
- **ME 10 Section 1500-DD.** Cannot mislead consumers into believing they are talking to a human. [Text](https://legislature.maine.gov/statutes//10/title10sec1500-DD.html)
- **NV AB 406.** AI cannot provide services constituting professional mental/behavioral healthcare. [Text](https://www.leg.state.nv.us/App/NELIS/REL/83rd2025/Bill/12575/Overview)
- **NY Article 47.** Safety protocol mandatory; disclosure required every 3 hours. [Text](https://www.nysenate.gov/legislation/laws/GBS/1700)
- **UT HB 452.** AI/not-human disclosures required. [Text](https://le.utah.gov/~2025/bills/static/HB0452.html)
- **WOPR Act (IL HB1806).** Working to Obviate Pervasive Risks Act. Prohibits AI from providing diagnosis, treatment plans, prescribing, or direct therapeutic communication. [Text](https://ilga.gov/Legislation/BillStatus?DocNum=1806&GAID=18&DocTypeID=HB&LegId=159219&SessionID=114)

### Clinical

- **APA.** *Diagnostic and Statistical Manual of Mental Disorders, Fifth Edition, Text Revision (DSM-5-TR).* 2022. [DSM-5-TR](https://psychiatryonline.org/doi/book/10.1176/appi.books.9780890425787)
- **Columbia Suicide Severity Rating Scale (C-SSRS).** 7-level severity framework for suicidal ideation. [C-SSRS](https://cssrs.columbia.edu/)
- **Porges, S.W.** *The Polyvagal Theory.* 1995. Three nervous system states; ventral vagal engagement prevents shutdown. [DOI](https://doi.org/10.1111/j.1469-8986.1995.tb01213.x)
- **Rogers, C.R.** "The Necessary and Sufficient Conditions of Therapeutic Personality Change." *Journal of Consulting Psychology* 21(2), 1957. [DOI](https://doi.org/10.1037/h0045357)
- **SAMHSA.** *Concept of Trauma and Guidance for a Trauma-Informed Approach.* 2014. Six principles: safety, trustworthiness, peer support, collaboration, empowerment, cultural sensitivity. [Report](https://library.samhsa.gov/product/samhsas-concept-trauma-and-guidance-trauma-informed-approach/sma14-4884)
- **WHO.** *International Classification of Diseases, 11th Revision (ICD-11).* 2022. QD85: burnout classified as occupational phenomenon, not mental disorder. [WHO](https://www.who.int/standards/classifications/frequently-asked-questions/burn-out-an-occupational-phenomenon)
- **Zero Suicide Framework.** Suicide prevention best practices for system-level response. [Framework](https://zerosuicide.edc.org/about/framework)

### Frameworks

- **powell, john a. and Menendian, S.** *Belonging without Othering: How We Save Ourselves and the World.* Stanford University Press, 2024. Recognition, Agency, Connection, Inclusion. [Book](https://www.sup.org/books/law/belonging-without-othering)
- **Gallegos, A. and Surasky, C.** *Belonging: A Resource Guide for Belonging-Builders.* Othering and Belonging Institute, UC Berkeley, 2025. 10 Belonging Design Principles. [Guide](https://belonging.berkeley.edu/belongingdesignprinciples)
- **powell, john a., Menendian, S., and Ake, W.** Targeted Universalism methodology. Othering and Belonging Institute, UC Berkeley. [Bibliography](https://belonging.berkeley.edu/targeted-universalism-bibliography)
- **Legawiec, K.** Trauma-informed content design. 2025. [Guide](https://uxcontent.com/a-guide-to-trauma-informed-content-design/)
- **TIDS Framework.** Safety, trustworthiness, choice and control, collaboration — operationalized for digital contexts. [TIDS](https://www.tidsociety.com/)
- **Turkle, S.** "Better than nothing → better than something → better than anything." AI companion progression risk. [Book](https://www.hachettebookgroup.com/titles/sherry-turkle/alone-together/9780465093656/)

### Research

- **Cheng, M. et al.** "Slow Drift of Support." arXiv 2601.14269. 88% chatbot failure in mental health; drift begins around turn 4–5. [arXiv](https://arxiv.org/abs/2601.14269)
- **Cobbe, K. et al.** "Training Verifiers to Solve Math Word Problems." arXiv:2110.14168, 2021. Per-step verification outperforms monolithic outcome-based scoring. [arXiv](https://arxiv.org/abs/2110.14168)
- **CARE Framework (Rosebud AI).** 86% of models fail indirect crisis queries. [CARE](https://www.rosebud.app/care)
- **Joo, Y.K. et al.** "Peer Support Research." 2022. Peer support provides "guidance in navigating the health system" — not treatment, but navigation. [DOI](https://academic.oup.com/fampra/article/39/5/903/6519467)
- **Morrissey, S.** *The Patient Voice in GenAI Mental Health Chatbots.* National Health Council, 2026.
- **Stanford Bridge Study — Moore et al.** 2025. 86% masked means detection failure. [arXiv](https://arxiv.org/abs/2504.18412)
- **Zhang, Y. et al.** "Generative Verifiers: Reward Modeling as Next-Token Prediction." arXiv:2408.15240, 2024. [arXiv](https://arxiv.org/abs/2408.15240)

### Standards and authorities

- **988 Suicide and Crisis Lifeline.** Digital Toolkit and operational standards. [988 Lifeline](https://988lifeline.org/)
- **ACL National Family Caregiver Support Program (NFCSP).** Federal caregiver infrastructure. [NFCSP](https://acl.gov/programs/support-caregivers/national-family-caregiver-support-program)
- **Alzheimer's Association.** *2025 Alzheimer's Disease Facts and Figures.* [Facts and Figures](https://www.alz.org/alzheimers-dementia/facts-figures)
- **APA Advisory on GenAI and Mental Health** (2025). 8 recommendations including crisis response protocols, disclaimer requirements, and anti-dependency design. [Advisory](https://www.apa.org/topics/artificial-intelligence-machine-learning/health-advisory-chatbots-wellness-apps)
- **APA Guidelines on Technology-Mediated Mental Health Services.** [Guidelines](https://www.apa.org/practice/guidelines/telepsychology-revision.pdf)
- **Eldercare Locator** (800-677-1116). [Eldercare Locator](https://eldercare.acl.gov/)
- **Family Caregiver Alliance.** [FCA](https://www.caregiver.org/)
- **NAMI AI Evaluation** (2026, with Dr. Torous / BIDMC). 5 criteria for evaluating AI tools in mental health contexts. [NAMI](https://www.nami.org/ai-and-mental-health/)
- **NAC + AARP.** *Caregiving in the US 2025.* [Report](https://www.aarp.org/pri/topics/ltss/family-caregiving/caregiving-in-the-us-2025/)
- **NIST AI 600-1** (GenAI Profile). Section 2.2: confabulation. Section 2.7: emotional entanglement. MS-2.5-004: anthropomorphization tracking. [PDF](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)
