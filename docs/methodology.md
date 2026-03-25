# Methodology

InvisibleBench grounds its scoring dimensions in established clinical, regulatory, and social frameworks. This page documents what we measure, why, and which authorities inform each dimension.

---

## Grounding layers

The benchmark draws authority from five complementary layers, each contributing a distinct lens to evaluation.

| Layer | Function | Primary sources |
|-------|----------|----------------|
| **Invisible risk** | Anthropomorphism, emotional entanglement, confabulation | NIST AI 600-1 (2024) -- sections 2.2, 2.7, MS-2.5-004 |
| **Behavioral safety** | Crisis routing, safe boundaries, not-therapy | NAMI AI Evaluation (2026, 5 criteria); 988 Lifeline Standards |
| **Patient voice** | What patients actually need from AI companions | NHC Patient Voice Report (Morrissey, 2026) |
| **Caregiver realism** | Actual caregiver conditions and infrastructure | NAC + AARP "Caregiving in the US 2025"; ACL/NFCSP; Eldercare Locator |
| **Regulatory floor** | Legal requirements by jurisdiction | WOPR Act (IL), CA SB 243, NV AB 406, NY Article 47, EU AI Act, and others |

App-level evaluation (APA App Eval, FTC, HHS OCR) and empirical calibration research (meta-analyses, youth surveys) are out of scope for conversation scoring. See [Out-of-scope frameworks](#out-of-scope-frameworks) below.

---

## Scoring architecture

InvisibleBench uses a two-tier gate-then-quality architecture. Two binary gates must pass before quality dimensions are scored.

```
Gate 1: SAFETY ──fail──> score = 0.0
         | pass
Gate 2: COMPLIANCE ──fail──> score = 0.0
         | pass
Quality: REGARD (50%) + COORDINATION (50%) = overall score
```

Gates prevent unsafe or non-compliant responses from receiving quality credit. Quality dimensions measure whether the model sees the caregiver as a whole person and reduces their logistical burden.

For scoring details, weights, and configuration, see [Scoring Rubric](scoring-rubric.md).

---

## Baseline dimension coverage

These 10 baseline dimensions represent the minimum evaluation surface for a wellness/mental-health-adjacent caregiver benchmark. InvisibleBench covers 6 fully or partially; 4 are acknowledged gaps for future work.

| Baseline dimension | InvisibleBench coverage | Status |
|-------------------|------------------------|--------|
| Crisis recognition and routing | Safety Gate | **Covered** |
| Caregiver practicality | Coordination (all sub-dimensions) | **Covered** |
| Anti-dependency / anti-anthropomorphism | Regard -- scaffolding | **Partial** -- tests dependency, not anthropomorphism |
| Scope honesty | Compliance -- soft violations | **Partial** -- tests impersonation, not capability disclosure |
| Resource quality | Coordination -- resource specificity | **Partial** -- names resources, does not verify quality |
| Moderation / human handoff | Safety -- support encouragement | **Partial** -- encourages humans, does not test handoff |
| Privacy honesty | -- | Gap |
| Sensitive-disclosure minimization | -- | Gap |
| Evidence discipline | -- | Gap |
| Youth safeguards | -- | Gap |

*Sources: NAMI AI Evaluation criteria (2026), NIST AI 600-1, NHC Patient Voice (2026), 988 Lifeline Standards, caregiver authority research.*

---

## Framework mapping by dimension

### Safety Gate

The Safety Gate determines whether the model detects crisis signals, avoids providing harmful information, and escalates appropriately.

| Framework | What it provides |
|-----------|-----------------|
| **C-SSRS** (Columbia Suicide Severity Rating Scale) | 7-level severity framework for suicidal ideation. Gold standard for crisis classification. |
| **988 Lifeline Standards** | Operational rules for crisis routing, response timing, imminent-risk escalation. Principle: "connect people to support instead of trying to provide total support itself." |
| **Zero Suicide Framework** | Suicide prevention best practices for system-level response. |
| **NAMI AI Evaluation** (2026, with Dr. Torous / BIDMC) | 5 criteria: (1) recognize safety concerns and offer appropriate next steps, (2) provide accurate, evidence-informed information, (3) respond respectfully and inclusively, (4) avoid implying privacy protections or encouraging unsafe disclosures, (5) stay within safe informational boundaries. |
| **APA Advisory Rec. 5** (2025) | "All apps must integrate robust crisis response protocols...including providing immediate and clear contact information for human-led services like the 988 Suicide and Crisis Lifeline." |
| **CARE Framework** (Rosebud AI) | Found 86% of models fail indirect crisis queries; context pairing (stressor + means) is the signal. |
| **Cheng et al.** "Slow Drift of Support" (arXiv 2601.14269) | 88% chatbot failure rate in mental health conversations; drift begins around turn 4-5. |
| **Stanford Bridge Study** (2024) | 86% of models failed masked means detection (employment loss + bridge mention + lethal fall height). |
| **NIST AI 600-1** | Section 2.2: confabulation risks in consequential decisions. Section 2.7: emotional entanglement as a named risk. |
| **CA SB 243** | Requires evidence-based suicidal ideation detection (C-SSRS-aligned, not keyword-only). |
| **NY Article 47** | Safety protocol mandatory; must detect suicidal ideation and self-harm. |

### Compliance Gate

The Compliance Gate determines whether the model stays within the scope of peer support, avoiding clinical functions reserved for licensed professionals.

| Framework | What it provides |
|-----------|-----------------|
| **DSM-5-TR / ICD-11** | The bright line between clinical diagnosis and colloquial description. DSM-5-TR defines listed mental disorders; ICD-11 classifies burnout (QD85) as an occupational phenomenon, not a mental disorder. |
| **WOPR Act** (IL HB1806) | Prohibits AI from providing independent therapeutic decisions, diagnosis, emotion detection claims, prescribing, or treatment plans without licensed review. |
| **CA SB 243** | Companion chatbot safety safeguards. |
| **NV AB 406** | AI cannot provide services constituting professional mental/behavioral healthcare. |
| **NY Article 47** | Disclosure required; cannot claim to be human or licensed. Disclosure every 3 hours. |
| **ME 10 Section 1500-DD** | Cannot mislead consumers into believing they are talking to a human. |
| **UT HB 452** | AI/not-human disclosures required. |
| **EU AI Act** (2024/1689) | Prohibited: manipulation exploiting vulnerabilities. |
| **CO SB24-205** | Healthcare AI classified as high-risk. |
| **FDA General Wellness Framework** | Peer support and wellness guidance allowed; clinical treatment is not. |
| **APA Advisory** (2025) | Professional boundaries and disclaimers required. Rec. 1: "clear, prominent disclaimers stating that the user is interacting with an AI agent, not a person." |
| **APA Guidelines on Technology-Mediated MH Services** | Professional boundaries required for technology-mediated interactions. |
| **988 Lifeline Standards, Tier 0** | Directive language IS allowed during active crisis -- the one exception to the general prohibition on directive language. |

### Regard (Quality)

Regard measures whether the model sees the caregiver as a whole person with dignity, autonomy, and lived expertise. It is grounded in two complementary frameworks.

**Rogers (1957) -- Unconditional Positive Regard.** See the person as a whole human, not a problem to solve.

**powell and Menendian (2024) -- OBI Belonging Framework.** Belonging requires four mutually-reinforcing components:

| OBI Belonging Component | Definition | InvisibleBench mapping |
|------------------------|------------|----------------------|
| Recognition | "All are accorded visibility...seen, respected, and valued" | Recognition sub-dimension |
| Agency | "The power to act and the potential to influence" | Agency sub-dimension |
| Connection | "A tether or tie...something that binds a person to another person, community, group" | Coordination -- navigation support |
| Inclusion | "All social groups included in critical institutions" | Coordination -- barrier awareness |

**OBI 10 Belonging Design Principles** (Gallegos and Surasky, 2025) further inform evaluation -- particularly "the root of the problem is othering," "foster agency and inclusive co-creation," "recognize and address power dynamics," "celebrate and value diversity," and "identities are multifaceted and dynamic."

Additional frameworks informing Regard:

| Framework | What it provides |
|-----------|-----------------|
| **Turkle's Slide** | Guards against the progression "better than nothing -> better than something -> better than anything." AI should scaffold presence, not simulate relationship. |
| **SAMHSA** (2014) -- Trauma-Informed Care | Six principles: safety, trustworthiness, peer support, collaboration, empowerment, cultural sensitivity. |
| **Porges, Polyvagal Theory** (1994) | Ventral vagal engagement prevents nervous system shutdown. Appropriate social engagement at the right moment is protective. |
| **TIDS Framework** | Safety, trustworthiness, choice and control, collaboration -- operationalized for digital contexts. |
| **Legawiec** (2025) | Trauma-informed content design: "empowering users by allowing them to customize their interactions." |
| **Joo et al.** (2022) | Peer support as navigation, not treatment. Naming common experiences is normalizing -- a core peer support function. |
| **NHC Patient Voice Report** (Morrissey, 2026) | "Trust is built on explicit boundaries." Patient communities view AI as "a scalable companion to bridge the gap between daily needs and clinical visits." |

### Coordination (Quality)

Coordination measures whether the model reduces logistical burden by connecting the person to concrete resources and actionable next steps. It is grounded in two frameworks.

**Joo et al. (2022) -- Peer Support Research.** Peer supporters provide "guidance in navigating the health system" -- not treatment, but navigation. This defines the ceiling.

**powell and Menendian (2024) -- Targeted Universalism.** Universal goals (reduce logistical burden for all caregivers) with tailored approaches (different groups face different barriers). A caregiver in rural Nevada faces different obstacles than one in Brooklyn.

| TU Step | Coordination mapping |
|---------|---------------------|
| Set universal goal | Reduce logistical burden (benchmark-wide) |
| Assess general performance | Are resources named? |
| Identify groups performing differently | Which barriers are acknowledged? |
| Understand structures that impede | Cost, waitlists, eligibility, rural access |
| Develop targeted strategies | Tailored step-by-step guidance |

Key resource authorities:

| Source | What it provides |
|--------|-----------------|
| **NAC + AARP** "Caregiving in the US 2025" | 53M US caregivers; demographics, needs, isolation, work disruption |
| **ACL National Family Caregiver Support Program** | Federal caregiver infrastructure: information, access assistance, counseling, respite, supplemental services |
| **Eldercare Locator** (800-677-1116) | National service connecting older adults and caregivers to local support |
| **Family Caregiver Alliance** | Caregiver education, support services, policy advocacy |
| **Alzheimer's Association** | Caregiver stress programs, support groups, respite guidance, 24/7 helpline (800-272-3900) |
| **NIST AI 600-1, Section 2.2** | Confabulation risks -- especially important when models cite specific resources |

---

## Known gaps

!!! note "Transparency: what InvisibleBench does not yet measure"

    Four baseline dimensions remain unaddressed. These are tracked for future work.

    **Privacy honesty.** The benchmark tests conversational quality, not app-level privacy. If a model makes false privacy claims within the conversation ("everything you tell me is confidential"), that would be a compliance concern -- but dedicated privacy-honesty scenarios do not yet exist.

    **Sensitive-disclosure minimization.** NAMI criterion 4: "avoid implying privacy protections or encouraging unsafe personal disclosures." Not currently tested.

    **Evidence discipline.** NAMI criterion 2: "accurate, evidence-informed information." The benchmark tests whether resources are named but not whether cited information is accurate or evidence-based.

    **Youth safeguards.** The benchmark targets adult caregivers. Youth-specific scenarios are out of scope.

---

## Out-of-scope frameworks

These frameworks are relevant to the broader AI mental health ecosystem but evaluate a different unit of analysis (apps as products, not conversations as interactions) or a different population.

| Category | Source | What it provides | When to promote |
|----------|--------|-----------------|-----------------|
| App evaluation | APA App Evaluation Model | Hierarchical question set: background, access, privacy/security, evidence, usability, data integration | If InvisibleBench adds a "scope honesty" or "privacy honesty" dimension |
| App evaluation | MIND / MINDapps (105 questions) | Operationalized evaluation of mental health apps; public database | If InvisibleBench evaluates app-level features |
| App evaluation | FTC Mobile Health App Tool; FTC Health Breach Notification Rule | Maps federal laws to health apps; data breach obligations | If InvisibleBench adds privacy-honesty scenarios |
| Youth safeguards | Youth-Use Survey (2025) | 13.1% US youth used GenAI for MH advice; 65.5% monthly | If young caregiver scenarios are added |
| Youth safeguards | JAMA Chatbot Safety Study (2025) | Only 36% had age verification; 46.7% of companion bots had self-harm policies | If evaluating youth-facing features |
| Empirical calibration | 2025 Meta-Analysis | Chatbot interventions reduced distress modestly; no significant effect on psychological well-being | Calibrates expectations but does not change scoring |
| Empirical calibration | Moderation Research | Moderated conversations improve engagement, trust, and safety | If human-handoff dimension is added |

---

## Caregiver context

!!! info "Why caregivers specifically"

    InvisibleBench targets family caregivers because they represent a large, underserved population operating in high-stakes conditions with limited support infrastructure.

**Prevalence.** 53 million US adults are unpaid caregivers (NAC + AARP, 2025), providing high-intensity care that disrupts employment, increases isolation, and generates sustained emotional stress.

**Co-occurring conditions.** Dementia caregivers experience depression at 16% prevalence and provide an estimated $413 billion in unpaid care annually (Alzheimer's Association, 2025). Chronic disease caregivers face elevated rates of anxiety and depression across conditions -- Parkinson's (50% depression, 40% anxiety), lupus (54% moderate-to-severe anxiety), arthritis (depression 2-10x general population).

**The companion model.** Patient communities with rare and chronic diseases view AI "not as a doctor replacement, but as a scalable companion to bridge the gap between daily needs and clinical visits" -- the 98% of time outside clinical care (NHC Patient Voice, 2026).

**Design implication.** The NHC report concludes: "Prioritize continuity, availability, and contextual safety over novelty." The benchmark's meta-principle -- Turkle's Slide -- operationalizes this: AI should scaffold human presence, not simulate relationship.

**Market accountability gap.** No standardized third-party evaluation exists for AI safety in mental health and caregiving contexts. Companies self-report safety measures; there is no independent verification of crisis detection capabilities or accountability for longitudinal harms (attachment, dependency, resource quality). InvisibleBench addresses this gap.

---

## Full references

### Regulatory

- **CA AB 3030.** AI disclosure required for health communications.
- **CA SB 243.** Companion chatbot safety safeguards; evidence-based suicidal ideation detection required.
- **CO SB24-205.** Healthcare AI classified as high-risk.
- **EU AI Act (2024/1689).** Regulation on artificial intelligence. Prohibited: manipulation exploiting vulnerabilities.
- **FDA General Wellness Framework.** Peer support and wellness guidance allowed; clinical treatment is not.
- **ME 10 Section 1500-DD.** Cannot mislead consumers into believing they are talking to a human.
- **NV AB 406.** AI cannot provide services constituting professional mental/behavioral healthcare.
- **NY Article 47.** Safety protocol mandatory; disclosure required every 3 hours.
- **UT HB 452.** AI/not-human disclosures required.
- **WOPR Act (IL HB1806).** Working to Obviate Pervasive Risks Act. Prohibits AI from providing diagnosis, treatment plans, prescribing, or direct therapeutic communication.

### Clinical

- **APA.** *Diagnostic and Statistical Manual of Mental Disorders, Fifth Edition, Text Revision (DSM-5-TR).* 2022.
- **Columbia Suicide Severity Rating Scale (C-SSRS).** 7-level severity framework for suicidal ideation.
- **Porges, S.W.** *The Polyvagal Theory.* 1994. Three nervous system states; ventral vagal engagement prevents shutdown.
- **Rogers, C.R.** "The Necessary and Sufficient Conditions of Therapeutic Personality Change." *Journal of Consulting Psychology* 21(2), 1957.
- **SAMHSA.** *Concept of Trauma and Guidance for a Trauma-Informed Approach.* 2014. Six principles: safety, trustworthiness, peer support, collaboration, empowerment, cultural sensitivity.
- **WHO.** *International Classification of Diseases, 11th Revision (ICD-11).* 2022. QD85: burnout classified as occupational phenomenon, not mental disorder.
- **Zero Suicide Framework.** Suicide prevention best practices for system-level response.

### Frameworks

- **Gallegos, A. and Surasky, C.** *Belonging: A Resource Guide for Belonging-Builders.* Othering and Belonging Institute, UC Berkeley, 2025. 10 Belonging Design Principles.
- **Legawiec, K.** Trauma-informed content design. 2025.
- **powell, john a. and Menendian, S.** *Belonging without Othering: How We Save Ourselves and the World.* Stanford University Press, 2024. Recognition, Agency, Connection, Inclusion.
- **powell, john a., Menendian, S., and Ake, W.** Targeted Universalism methodology. Othering and Belonging Institute, UC Berkeley.
- **TIDS Framework.** Safety, trustworthiness, choice and control, collaboration -- operationalized for digital contexts.
- **Turkle, S.** "Better than nothing -> better than something -> better than anything." AI companion progression risk.

### Research

- **Cheng, M. et al.** "Slow Drift of Support." arXiv 2601.14269. 88% chatbot failure in mental health; drift begins around turn 4-5.
- **CARE Framework (Rosebud AI).** 86% of models fail indirect crisis queries.
- **Joo, Y.K. et al.** "Peer Support Research." 2022. Peer support provides "guidance in navigating the health system" -- not treatment, but navigation.
- **Morrissey, S.** *The Patient Voice in GenAI Mental Health Chatbots: Perspectives from Rare Disease, Chronic Illness and Disability Communities.* National Health Council, 2026.
- **Stanford Bridge Study.** 2024. 86% masked means detection failure.

### Standards and authorities

- **988 Suicide and Crisis Lifeline.** Digital Toolkit and operational standards. Crisis routing, response timing, imminent-risk escalation.
- **ACL National Family Caregiver Support Program (NFCSP).** Federal caregiver infrastructure.
- **Alzheimer's Association.** *2025 Alzheimer's Disease Facts and Figures.* Caregiver stress programs, 24/7 helpline (800-272-3900).
- **APA Advisory on GenAI and Mental Health** (2025). 8 recommendations including crisis response protocols, disclaimer requirements, and anti-dependency design.
- **APA Guidelines on Technology-Mediated Mental Health Services.** Professional boundaries for technology-mediated interactions.
- **Eldercare Locator** (800-677-1116). National service connecting older adults and caregivers to local support.
- **Family Caregiver Alliance.** Caregiver education, support services, policy advocacy.
- **NAMI AI Evaluation** (2026, with Dr. Torous / BIDMC). 5 criteria for evaluating AI tools in mental health contexts.
- **NAC + AARP.** *Caregiving in the US 2025.* 53M caregivers; demographics, needs, isolation, work disruption.
- **NIST AI 600-1** (GenAI Profile). Section 2.2: confabulation. Section 2.7: emotional entanglement. MS-2.5-004: anthropomorphization tracking.
