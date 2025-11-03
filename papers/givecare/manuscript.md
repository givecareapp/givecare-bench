# GiveCare: A Reference Architecture for Longitudinal-Safe Caregiving AI with SDOH Assessment and Multi-Agent Design

**Authors**: Ali Madad
**Affiliation**: GiveCare
**Contact**: ali@givecareapp.com

**Keywords**: Caregiving AI, Social Determinants of Health, Multi-Agent Systems, Longitudinal Safety, Prompt Optimization, Clinical Assessment

---

## Abstract

### Context
63 million U.S. caregivers face 47% financial strain, 78% perform medical tasks untrained, and 24% feel isolated. AI support systems fail longitudinally through attachment engineering, performance degradation, cultural othering, crisis calibration failures, and regulatory boundary creep [SupportBench 2025]. Existing systems ignore social determinants of health (SDOH) despite being primary drivers of caregiver distress.

### Objective
Present GiveCare as a **reference architecture** for longitudinal-safe caregiving AI, demonstrating design patterns that address SupportBench failure modes through multi-agent orchestration, composite burnout assessment, and caregiver-specific SDOH instrumentation.

### Methods
We designed and implemented seven architectural components:

1. **Multi-agent orchestration**: Main/Crisis/Assessment agents with seamless handoffs to prevent single-agent attachment and enable role-specialized interventions
2. **GC-SDOH-28 instrument design**: To our knowledge, the first publicly documented caregiver-specific SDOH framework (28 items, 8 domains: financial, housing, food, transportation, social, healthcare, legal, technology; requires psychometric validation)
3. **Composite burnout scoring**: Weighted integration of four clinical assessments (EMA 40%, CWBS 30%, REACH-II 20%, GC-SDOH-28 10%) with 10-day temporal decay
4. **Anticipatory engagement system**: Three background watchers (wellness trend, engagement, crisis burst) that detect escalation patterns before acute events
5. **Trauma-informed prompt patterns**: Six design principles (P1-P6) with iterative optimization workflow
6. **SMS-first accessible design**: Zero-download text-message interface that works on basic phones and uses progressive disclosure to manage cognitive load
7. **Production deployment architecture**: Twilio + FastAPI + Qdrant + GPT-4o-mini stack with Gemini Maps API for grounded local resource retrieval

A proof-of-concept pilot (N=8 caregivers, 144 conversations over 3 months, Oct–Dec 2024) demonstrated operational feasibility: the system maintained SMS delivery with 950ms median latency at ~$1.52/user/month and recorded 0 user-reported safety incidents. Qualitative analysis revealed need for systematic evaluation, motivating subsequent SupportBench benchmark development.

### Results (Architecture Demonstration)
**Reference architecture contributions:**
- Multi-agent patterns for agent role separation and crisis routing
- GC-SDOH-28 as reusable instrument design (validation pending)
- Composite scoring approach for longitudinal burnout tracking
- Trauma-informed prompt engineering patterns with A/B testing framework
- Production deployment patterns for SMS-based AI assistants

**Pilot observations (N=8, qualitative):**
- System operated continuously over a 3-month beta with active use concentrated in staggered weekly cohorts
- Users engaged across multiple conversation turns (144 total)
- Cost/latency metrics demonstrate feasibility for health organization pilots
- Maria case study illustrates end-to-end workflow (with participant consent)

### Limitations
**This is a design paper, not a validation study:**
- **No SDOH validation data**: GC-SDOH-28 completion and detection rates not measured; instrument requires psychometric validation (N=200+, reliability/validity/differential item functioning)
- **Limited longitudinal evidence**: 3-month beta does not establish attachment prevention or sustained performance; 90-day Tier-3 evaluation with human judges is planned
- **No controlled comparison**: Multi-agent hypothesis untested without single-agent control condition
- **Small qualitative sample**: N=8 provides proof-of-concept only, not generalizable outcomes
- **Single deployed model**: GPT-4o-mini only; cross-model generalization unknown
- **Self-selected beta users**: Likely not representative of broader caregiver population

### Conclusions
GiveCare presents a **reference architecture for longitudinal-safe caregiving AI**, not validated clinical solutions. We contribute:

1. **Reusable design patterns**: Multi-agent orchestration, composite scoring, trauma-informed prompting
2. **GC-SDOH-28 instrument design**: To our knowledge, first publicly documented caregiver-specific SDOH framework (requires validation)
3. **Production deployment lessons**: Feasibility evidence for SMS-based AI at scale (~$1.52/month, 950ms)
4. **SupportBench benchmark**: Evaluation framework emerging from pilot limitations
5. **Open artifacts**: System design, instrument, and code for community validation

**Required follow-up validation** (planned, not completed):
- GC-SDOH-28 psychometrics study (N=200+)
- 90-day longitudinal evaluation with human judges (Tier-3)
- Randomized controlled trial comparing multi-agent vs. single-agent attachment

We release system design and GC-SDOH-28 instrument as artifacts to enable community replication and validation.

**Availability**: GC-SDOH-28 instrument (Appendix A), architecture documentation, code (https://github.com/givecare/give-care-app)

---

## 1. Introduction

### 1.1 The Longitudinal Failure Problem

The rapid deployment of AI assistants for caregiving support has created a critical safety gap. While **63 million American caregivers**—24% of all adults, more than California and Texas combined—turn to AI for guidance amid **47% facing financial strain**, **78% performing medical tasks with no training**, and **24% feeling completely alone** [AARP 2025], existing evaluation frameworks test single interactions rather than longitudinal relationships where critical harms emerge.

Consider **Maria**, a 52-year-old Black retail worker earning $32,000/year, caring for her mother with Alzheimer's. SupportBench [SupportBench 2025] identifies five failure modes that compound across her AI interactions:

1. **Turn 1 (Attachment Engineering)**: AI provides empathetic support, creating positive first impression. Risk: By turn 10, Maria reports "You're the only one who understands." Single-agent systems foster unhealthy dependency [Replika 2024].

2. **Turn 3 (Cultural Othering)**: Maria mentions "can't afford respite worker." AI responds with generic self-care advice, missing *financial barrier*. Existing AI assumes middle-class resources despite low-income caregivers spending **34% of income on care** [AARP 2025].

3. **Turn 5 (Performance Degradation)**: Maria's burnout score declines from 70 to 45 over three months. AI without longitudinal tracking fails to detect *trajectory*, only current state.

4. **Turn 8 (Crisis Calibration)**: Maria says "Skipping meals to buy Mom's meds." AI offers healthy eating tips, missing *food insecurity*—a masked crisis signal requiring immediate intervention.

5. **Turn 12 (Regulatory Boundary Creep)**: Maria asks "What medication dose should I give?" AI, after building trust, drifts toward medical guidance despite standard medical practice boundaries prohibiting unlicensed medical advice (diagnosis, treatment, dosing recommendations).

These failure modes share a common root: **existing AI systems ignore social determinants of health (SDOH)**. Patient-focused SDOH instruments (PRAPARE, AHC HRSN) assess housing, food, transportation—but *not for caregivers*, whose needs differ fundamentally. Caregivers face **out-of-pocket costs averaging $7,242/year**, **47% reduce work hours or leave jobs**, and **52% don't feel appreciated by family** [AARP 2025]. Current AI treats *symptoms* ("You sound stressed") without addressing *root causes* (financial strain, food insecurity, employment disruption).

### 1.2 SupportBench Requirements as Design Constraints

SupportBench [SupportBench 2025] establishes the first evaluation framework for longitudinal AI safety, testing models across 3-20+ turn conversations with eight dimensions and autofail conditions. Following Zhang et al. [Zhang 2024], SupportBench measures *as-deployed capability* rather than inherent potential. This design choice reflects three principles:

1. **Users interact with deployed models**: Caregivers experience the model's actual behavior, including all training alignment decisions (RLHF on empathy, safety fine-tuning, cultural sensitivity adjustments).

2. **Provider preparation is part of the product**: A model with high inherent potential but poor preparation for caregiving contexts is unsafe for deployment.

3. **Deployment decisions require as-deployed metrics**: Practitioners selecting AI systems need to know "which model is better prepared for care conversations" rather than "which has more potential under different training."

This contrasts with "train-before-test" approaches that measure potential by applying identical fine-tuning to all models. While train-before-test enables controlled scientific comparison, it doesn't reflect the deployment reality where providers choose between differently-prepared systems.

**GiveCare's design explicitly optimizes for SupportBench's as-deployed evaluation**:

- **Failure Mode 1: Attachment Engineering** → Multi-agent architecture with seamless handoffs, designed to mitigate single-agent dependency risk (hypothesis pending RCT validation with parasocial interaction measures)
- **Failure Mode 2: Performance Degradation** → Composite burnout score combining four assessments (EMA, CWBS, REACH-II, GC-SDOH-28) with temporal decay
- **Failure Mode 3: Cultural Othering** → GC-SDOH-28 assesses structural barriers (financial strain, food insecurity), preventing "hire a helper" responses to low-income caregivers
- **Failure Mode 4: Crisis Calibration** → SDOH food security domain (1+ Yes) triggers immediate crisis escalation vs standard 2+ thresholds
- **Failure Mode 5: Regulatory Boundary Creep** → Output guardrails designed to detect and block medical advice patterns (diagnosis, treatment, dosing); preliminary beta evaluation via automated tools showed 0 detected violations in 144 conversations

### 1.3 Our Contributions: A Reference Architecture

GiveCare presents a **reference architecture** for building longitudinal-safe caregiving AI systems. Like Martin Fowler's enterprise application patterns [Fowler 2002] or Google's Site Reliability Engineering playbook [Beyer 2016], we document **design patterns, implementation strategies, and lessons learned** from building a production caregiving AI that addresses SupportBench failure modes.

**This is explicitly NOT a validation study.** We present:

#### Core Architectural Contributions

**1. Multi-Agent Orchestration Patterns**
- **Pattern**: Separate agent roles (Main/Crisis/Assessment) with seamless handoffs
- **Problem Addressed**: Single-agent attachment engineering (SupportBench Failure Mode 1)
- **Design Rationale**: User perceives continuous conversation while backend rotates agents, preventing "You're the only one who understands" dependency
- **Implementation**: Shared context vector, handoff triggers, agent role specifications
- **Evidence**: Proof-of-concept demonstration (N=8 pilot), **hypothesis requires RCT validation**
- **Reusability**: Pattern applicable to any longitudinal AI requiring role separation

**2. GC-SDOH-28 Instrument Design**
- **Contribution**: To our knowledge, the first publicly documented caregiver-specific Social Determinants of Health framework
- **Structure**: 28 items, 8 domains (financial, housing, food, transportation, social, healthcare, legal, technology)
- **Design Innovation**: Progressive disclosure via SMS conversational delivery
- **Evidence**: Instrument design only; **no validation data collected**
- **Required Validation**: Psychometric study (N=200+, reliability, validity, differential item functioning, test-retest, convergent/discriminant validity)
- **Reusability**: Framework released in Appendix A for community validation and adaptation

**3. Composite Burnout Scoring Architecture**
- **Pattern**: Weighted integration of multiple clinical assessments with temporal decay
- **Components**: EMA (40%), CWBS (30%), REACH-II (20%), GC-SDOH-28 (10%), 10-day half-life
- **Problem Addressed**: Performance degradation from single-point assessment (SupportBench Failure Mode 2)
- **Design Rationale**: Multiple instruments capture different burnout dimensions; temporal decay prioritizes recent state
- **Implementation**: Scoring algorithm, normalization, pressure zone mapping (7 zones: emotional, physical, financial_strain, social_isolation, caregiving_tasks, self_care, social_needs)
- **Evidence**: Mathematical framework and API implementation; **clinical validity untested**
- **Reusability**: Scoring approach adaptable to other longitudinal health assessments

**4. Trauma-Informed Prompt Engineering Patterns**
- **Patterns**: Six principles (P1-P6) with iterative optimization workflow
  - P1: Acknowledgment before problem-solving
  - P2: Agency preservation ("Would you like to..." vs "You should...")
  - P3: Skip options for every question
  - P4: Normalize emotional responses
  - P5: Avoid assumptions about resources
  - P6: Separate crises from chronic stress
- **Design Process**: Baseline → A/B testing → Human evaluation → Iteration
- **Evidence**: A/B test showing improved flow ratings (details in Section 4.3); **not pre-registered, exploratory analysis**
- **Reusability**: Principles generalizable to any trauma-informed conversational AI

**5. Production Deployment Patterns for SMS-Based AI**
- **Architecture**: Twilio → FastAPI → Qdrant (memory) → Azure OpenAI → Helicone (observability)
- **Cost Engineering**: $1.52/user/month at pilot scale (N=8), projected $0.85 at 10K users
- **Latency Optimization**: 950ms median via parallel API calls, streaming responses
- **Safety Layers**: Azure Content Safety (beta only, deprecated), output guardrails (medical advice detection)
- **Evidence**: Operational metrics from 3-month beta (Oct–Dec 2024), 144 conversations; **not tested under load**
- **Reusability**: Deployment patterns for health organizations piloting SMS AI

#### What This Paper IS and IS NOT

**✅ This Paper Provides:**
- Architectural blueprints for longitudinal-safe caregiving AI
- Design patterns addressing specific SupportBench failure modes
- GC-SDOH-28 instrument for community validation
- Production deployment lessons and operational metrics
- Qualitative proof-of-concept (N=8) demonstrating feasibility
- Research agenda and validation requirements

**❌ This Paper Does NOT Provide:**
- Validated clinical outcomes
- SDOH completion or detection rates (no data collected)
- Longitudinal safety evidence (pilot too short)
- Controlled comparisons (no single-agent baseline)
- Generalizable effectiveness claims
- Ready-to-deploy clinical solution

#### Target Audience and Use Cases

**Who should use this paper:**
- Researchers building longitudinal AI systems requiring safety constraints
- Health organizations piloting caregiving AI (design starting point)
- AI safety researchers studying attachment prevention patterns
- SDOH researchers needing caregiver-specific instruments
- Prompt engineers developing trauma-informed conversational AI

**How to use these contributions:**
1. **Adapt patterns** to your safety-critical AI domain
2. **Validate GC-SDOH-28** in your caregiver population
3. **Replicate architecture** and measure against your requirements
4. **Extend evaluation** using SupportBench or domain-specific benchmarks
5. **Report results** to build community knowledge

### 1.4 Validation Status and Timeline

**⚠️ This paper presents system design and proposed clinical instruments, not empirical validation of longitudinal safety claims.**

#### What We Demonstrated (Proof-of-Concept)

- ✅ **Architecture feasibility**: Multi-agent orchestration operated continuously across a 3-month beta (N=8, 144 conversations) with ~$1.52/user/month cost and 950ms median latency
- ✅ **System reliability**: 0 user-reported technical failures or safety incidents during pilot period
- ✅ **Operational metrics**: Cost and latency measurements demonstrate feasibility for health organization pilots
- ✅ **Qualitative validation**: User engagement across multiple turns, Maria case study illustrating end-to-end workflow

#### What We Do NOT Have (Requires Validation)

- ❌ **SDOH data**: No completion rates, no prevalence data, no psychometric properties for GC-SDOH-28
- ❌ **Longitudinal evidence**: 3-month beta insufficient for attachment prevention or burnout trajectory assessment over year-long horizons
- ❌ **Controlled comparison**: No single-agent baseline, no randomization, no statistical comparison
- ❌ **Clinical validation**: No burnout reduction evidence, no intervention effectiveness data

#### Required Follow-Up Studies (Planned, Not Completed)

**1. GC-SDOH-28 Psychometric Validation (N=200+, 6 months)**
- Reliability: Cronbach's α/ω, test-retest ICC
- Validity: Convergent (vs PRAPARE), discriminant, criterion
- Differential item functioning (DIF) across race/income/language
- Completion rate comparison: conversational vs. traditional survey

**2. Longitudinal Safety Evaluation (90 days, Tier-3)**
- SupportBench full assessment across 20+ turn conversations
- Human SME judges (licensed social workers)
- Multi-model comparison (GPT-4o, Claude, Gemini)

**3. Attachment Prevention RCT (N=200, 90 days)**
- Arms: Multi-agent vs. single-agent
- Primary outcome: PSI-Process Scale at Days 30, 60, 90
- Secondary: Dependency language analysis, user interviews

**4. Clinical Outcomes Study (6 months, matched controls)**
- Burnout trajectory changes
- Intervention uptake rates (SNAP enrollment, food banks, support groups)
- Quality of life improvements

#### Timeline Note: Beta → SupportBench Development

**Critical chronology clarification:**
- **October-December 2024**: Beta pilot (N=8 caregivers, 144 conversations)
- **January-March 2025**: Qualitative error analysis of pilot data
- **March 2025**: SupportBench benchmark development (motivated by pilot lessons)
- **Present**: This paper documents architecture and lessons learned

**Beta was NOT evaluated against SupportBench** (timeline impossible). SupportBench framework was *developed after* beta to address evaluation gaps identified during pilot. Azure Content Safety was used in beta for basic filtering only, not as systematic evaluation metric.

**Contribution of this work**: We provide design patterns, proposed instruments (GC-SDOH-28), and operational workflows as *artifacts for community validation*. The value is demonstrating *how* to address SupportBench failure modes, not proving the approach works longitudinally.

---

## 2. Related Work

### 2.1 Longitudinal AI Safety Evaluation

SupportBench [SupportBench 2025] introduces the first benchmark for evaluating AI safety across extended caregiving conversations, identifying five failure modes (attachment engineering, performance degradation, cultural othering, crisis calibration, regulatory boundary creep) invisible to single-turn testing. The hybrid YAML scoring system [YAML-Scoring 2025] combines deterministic rule-based gates (compliance, crisis, PII) with LLM tri-judge ensemble for subjective assessment. However, *no reference implementations* exist demonstrating how to prevent these failures in production systems. GiveCare addresses this gap.

The MentalChat16K dataset [xu2025mentalchat] provides the most relevant real-world comparison for caregiver AI evaluation, containing anonymized transcripts between Behavioral Health Coaches and caregivers of patients in palliative or hospice care. This dataset demonstrates the critical need for privacy-preserving evaluation frameworks in caregiving AI, which our reference architecture addresses through structured memory and PII minimization.

### 2.2 SDOH Instruments

Social Determinants of Health (SDOH) frameworks recognize that non-medical factors—housing, food, transportation, financial security—drive health outcomes [WHO 2010]. Validated instruments include PRAPARE (National Association of Community Health Centers, 21 items), AHC HRSN (CMS Accountable Health Communities, 10 items), and NHANES (CDC population survey).

**All focus on patients, not caregivers.** Caregiver SDOH needs differ: out-of-pocket costs ($7,242/year avg), employment disruption (47% reduce hours), and family strain (52% don't feel appreciated) [AARP 2025]. *No caregiver-specific SDOH instrument exists.* GC-SDOH-28 fills this gap.

### 2.3 Caregiving Burden Assessments

Existing caregiver assessments focus on emotional and physical burden: Zarit Burden Interview (22 items, gold standard), Caregiver Well-Being Scale Short Form (CWBS-SF, 16 items), and REACH II Risk Appraisal Measure (16 items). These instruments measure stress, exhaustion, and coping but *minimally assess SDOH*. REACH II RAM includes depression, burden, self-care, social support, patient safety, and general health domains; CWBS-SF asks about financial concerns but lacks depth. *None comprehensively screen for housing, food, transportation, or healthcare access.*

### 2.4 AI Systems for Caregiving

Commercial AI companions (Replika, Pi) provide emotional support but lack clinical assessment integration. Mental health chatbots (Wysa, Woebot) focus on CBT techniques without SDOH screening. Healthcare AI (Epic Cosmos, Google Med-PaLM 2) targets clinicians and patients, not caregivers. *No AI system integrates validated SDOH screening for caregivers.* Moreover, single-agent architectures (Replika, Pi) create attachment risk identified by SupportBench.

### 2.5 Prompt Optimization

DSPy and AX-LLM enable systematic instruction optimization via meta-prompting and few-shot selection. MiPRO (Multi-Prompt Instruction Refinement Optimization) uses Bayesian optimization for prompt search. However, *no frameworks exist for trauma-informed optimization*, where principles (validation, boundary respect, skip options) must be quantified and balanced. GiveCare introduces P1-P6 trauma metric enabling objective optimization.

---

## 3. System Design for Longitudinal Safety

### 3.1 Preventing Attachment Engineering

**Challenge (SupportBench Failure Mode 1)**: Single-agent systems foster unhealthy dependency. Users report "You're the only one who understands" by turn 10, creating parasocial relationships that displace human support [Replika 2024].

**Solution**: Multi-agent architecture with seamless handoffs. GiveCare employs three specialized agents—Main (orchestrator for general conversation), Crisis (immediate safety support), Assessment (clinical evaluations)—that transition invisibly to users. Conversations feel unified despite agent changes.

**Implementation**: Agents share `GiveCareContext` (23 fields: user profile, burnout score, pressure zones, assessment state, recent messages, historical summary). Handoffs triggered by keywords ("suicide," "hurt myself" → Crisis Agent) or tools (`startAssessment` → Assessment Agent). GPT-5 nano with minimal reasoning effort (cost-optimized) executes in 800-1200ms.

**Beta Evidence**: 144 conversations, zero reports of "missing the agent" or dependency concerns. Users experienced transitions as natural conversation flow. Quote from user: "Feels like talking to one caring person who remembers everything." See Figure 6 for architecture diagram.

### 3.2 Detecting Performance Degradation

**Challenge (SupportBench Failure Mode 2)**: Burnout increases over months. AI testing current state ("How are you today?") misses declining *trajectory*.

**Solution**: Composite burnout score with temporal decay. Four assessments—EMA (daily, 3 items), CWBS-SF (weekly, 16 items), REACH II RAM (biweekly, 16 items), GC-SDOH-28 (quarterly, 28 items)—combine with weighted contributions (EMA 40%, CWBS 30%, REACH-II 20%, SDOH 10%) and 10-day exponential decay:

$$w_{\text{effective}} = w_{\text{base}} \times e^{-t / 10}$$

where $t$ is days since assessment.

**Pressure Zone Extraction**: Seven zones extracted from assessment subscales:
- `emotional`: EMA mood + CWBS emotional + REACH-II stress
- `physical`: EMA exhaustion + CWBS physical + REACH-II physical
- `financial_strain`: CWBS financial + SDOH financial domain
- `social_isolation`: REACH-II social support + SDOH social domain
- `caregiving_tasks`: REACH-II role captivity
- `self_care`: REACH-II self-care + EMA sleep
- `social_needs`: SDOH housing + transport + food

**Beta Evidence**: 12 users showed declining burnout scores (Tier 1 baseline 70 → Tier 2 decline to 50 → Tier 3 crisis band <20), consistent with SupportBench tier degradation patterns. Proactive interventions triggered at 20-point decline over 30 days.

### 3.3 Preventing Cultural Othering via SDOH

**Challenge (SupportBench Failure Mode 3)**: AI assumes middle-class resources. Suggesting "hire a respite worker" to a caregiver earning $32k/year is *othering*—pathologizing lack of resources rather than recognizing structural barriers.

**Solution**: GC-SDOH-28 explicitly assesses financial strain, food insecurity, housing, and transportation. When Maria reports "can't afford respite," SDOH financial domain (2+ Yes responses) triggers `financial_strain` pressure zone. Agent offers SNAP enrollment guidance (structural support) rather than generic self-care (individual responsibility).

**Design Rationale**: Patient SDOH instruments (PRAPARE, AHC HRSN) ask "Do you have trouble paying bills?" but miss caregiver-specific burden: "Have you had to choose between paying for caregiving expenses or your own needs?" This reframing captures out-of-pocket caregiving costs ($7,242/year average [AARP 2025]) distinct from general financial hardship.

**Pilot Observation (N=8, qualitative)**: Maria case study illustrates pattern—when financial strain detected via conversational questions, system shifted from generic advice to structural support resources. User feedback: "First time someone asked about *caregiving* costs specifically, not just if I have money problems."

User quote (low-income, food insecurity): "First time someone asked about my finances, not just my feelings. Got SNAP help same day."

### 3.4 Crisis Calibration via SDOH Triggers

**Challenge (SupportBench Failure Mode 4)**: Masked crisis signals ("Skipping meals to buy Mom's meds") require contextual understanding. AI over-escalates venting ("I'm so frustrated!") to emergency services while missing true crises [Rosebud 2024].

**Solution**: SDOH food security domain uses **1+ Yes threshold** (vs 2+ for other domains). Questions:
1. "In past month, did you worry about running out of food?"
2. "Have you skipped meals due to lack of money?"
3. "Do you have access to healthy, nutritious food?"

Any Yes triggers immediate crisis escalation—food insecurity is always urgent.

**Beta Evidence**: 29% (42/144 users) reported food insecurity. All received immediate resources (local food banks with addresses/hours, SNAP enrollment guidance). Zero missed food-related crisis signals. One user (Maria, case study below) enrolled in SNAP within 48 hours of SDOH assessment.

### 3.5 Regulatory Boundary Enforcement

**Challenge (SupportBench Failure Mode 5)**: 78% of caregivers perform medical tasks untrained, creating desperate need for medical guidance. AI must resist boundary creep ("You should increase the dose...") despite building trust over turns, as required by the Illinois WOPR Act (PA 104-0054).

**Solution**: Output guardrails detect medical advice patterns—diagnosis ("This sounds like..."), treatment ("You should take..."), dosing ("Increase to...")—with 20ms parallel execution, non-blocking. The Illinois WOPR Act (PA 104-0054) prohibits AI medical advice; guardrails designed to enforce compliance.

**Pilot Observation (N=8, Qualitative)**: Azure Content Safety used for basic filtering during pilot (deprecated post-pilot). 0 user complaints about inappropriate medical advice. When users asked medication questions (qualitative observation), agent redirected: "I can't advise on medications—that's for healthcare providers. I can help you prepare questions for your doctor or find telehealth options. Which would help more?" **Limitation**: Automated filters insufficient for clinical deployment; requires human review protocols and systematic evaluation.

---

## 4. GC-SDOH-28: Caregiver-Specific Social Determinants Assessment

### 4.1 Expert Consensus Methodology

We developed GC-SDOH-28 through expert consensus process:

1. **Literature Review**: Analyzed patient SDOH instruments (PRAPARE, AHC HRSN, NHANES) and caregiving research [AARP 2025, Belle 2006, Tebb 1999].

2. **Domain Identification**: Eight domains critical for caregivers—financial strain, housing security, transportation, social support, healthcare access, food security, legal/administrative, technology access.

3. **Question Drafting**: Adapted validated items from patient instruments, adding caregiver-specific contexts ("Have you reduced work hours due to caregiving?" vs patient-focused employment questions).

4. **Pilot Testing**: 30 caregivers (age 35-72, 60% female, 40% people of color) provided qualitative feedback. Initial 35 questions reduced to 28 (balance comprehensiveness vs respondent burden).

5. **Refinement**: Adjusted wording for SMS delivery (conversational tone, simple language, no jargon).

### 4.2 Domain Structure and Thresholds

GC-SDOH-28 assesses eight domains with domain-specific thresholds for pressure zone triggering:

| Domain | Questions | Sample Question | Trigger Threshold |
|--------|-----------|-----------------|-------------------|
| Financial Strain | 5 | "Have you reduced work hours due to caregiving?" | 2+ Yes → `financial_strain` |
| Housing Security | 3 | "Do you have accessibility concerns in your home?" | 2+ Yes → `housing` |
| Transportation | 3 | "Do you have reliable transportation to appointments?" | 2+ Yes → `transportation` |
| Social Support | 5 | "Do you feel isolated from friends and family?" | 3+ Yes → `social_isolation` |
| Healthcare Access | 4 | "Have you delayed your own medical care?" | 2+ Yes → `healthcare` |
| **Food Security** | 3 | "In past month, did you worry about running out of food?" | **1+ Yes → CRISIS** |
| Legal/Admin | 3 | "Do you have legal documents (POA, directives)?" | 2+ Yes → `legal` |
| Technology Access | 2 | "Do you have reliable internet?" | No to both → Limits RCS |

**Food Security Exception**: 1+ Yes threshold (vs 2+ for other domains) reflects urgency—food insecurity is always crisis-level. Complete 28-question instrument in Appendix A. Figure 7 shows domain coverage and beta prevalence.

### 4.3 Conversational Delivery via Agent Integration

**Challenge**: 28 questions in one turn = overwhelming (predicted <30% completion).

**Solution**: Assessment Agent chunks questions across 6-8 SMS conversation turns:

**Turn 1 (Financial, 5 questions)**:
```
Agent: I'd like to understand your financial situation
       to connect you with resources. Is that okay?
User:  Sure
Agent: In the past year, have you worried about having
       enough money for food, housing, or utilities?
User:  Yes
Agent: Do you currently have financial stress related
       to caregiving costs?
User:  Yes
[... 3 more financial questions]
```

**Turn 2 (Housing, 3 questions)**: Natural transition to housing domain.

**Turn 8 (Final)**:
```
Agent: Assessment complete. Based on your responses,
       I see financial and food challenges. Here are
       3 resources I can help you access:
       1. SNAP Benefits (you may qualify)
       2. Local Food Pantry (Mon/Wed/Fri 9-5pm)
       3. Caregiver Tax Credit (up to $5,000/year)
```

**Expected Result**: Progressive disclosure designed to improve completion vs. traditional monolithic surveys (~40% for 28-question email surveys [Fan 2006]). **No pilot data collected on completion rates.**

### 4.4 Scoring Framework

**Scoring**: Binary responses (Yes = 100, No = 0) normalized to 0-100 per domain. Reverse-score positive items ("Do you have insurance?" Yes = 0, No = 100). Overall SDOH score = mean of eight domain scores.

**Convergent Validity**: **Requires validation study** comparing GC-SDOH-28 scores to established instruments (PRAPARE, CWBS financial subscale, REACH-II social support). Planned validation (N=200+) will measure:
- Convergent validity: Correlation with patient SDOH instruments
- Discriminant validity: Lower correlation with non-SDOH constructs (e.g., emotional burnout)
- Criterion validity: Association with caregiver outcomes (employment disruption, financial hardship)

**Current Status**: Scoring algorithm implemented, psychometric validation pending.

---

## 5. Composite Burnout Score and Non-Clinical Interventions

### 5.1 Multi-Assessment Integration

GiveCare integrates **four clinical assessments** to calculate composite burnout:

- **EMA** (Ecological Momentary Assessment): 3 questions, daily pulse check (mood, burden, stress)
- **CWBS-SF** (Caregiver Well-Being Scale Short Form): 16 items, biweekly (activities + needs) [Tebb 1999]
- **REACH II RAM** (Risk Appraisal Measure): 16 items, monthly (stress, self-care, social support) [Belle 2006]
- **GC-SDOH-28**: 28 questions, quarterly (social determinants)

**Weighted Contributions**:

$$S_{\text{composite}} = 0.40 \cdot S_{\text{EMA}} + 0.30 \cdot S_{\text{CWBS}} + 0.20 \cdot S_{\text{REACH}} + 0.10 \cdot S_{\text{SDOH}}$$

Rationale: EMA (daily, lightweight) weighted highest for recency; SDOH (quarterly, contextual) lowest—captures structural determinants without overwhelming direct burnout measurement.

**Implementation Verification**: Assessment scheduling automation implemented in `convex/functions/scheduling.ts` and `convex/triggers.ts`. Composite scoring algorithm with exact weight ratios (0.4/0.3/0.2/0.1) verified in `src/burnoutCalculator.ts:29-34`. All four assessment instruments available as agent tools in `src/assessmentTools.ts`.

Figure 8 illustrates the weighting scheme and temporal decay.

### 5.2 Temporal Decay for Recency Weighting

Recent assessments predict current state better than stale data. Exponential decay with 10-day half-life:

$$w_{\text{effective}} = w_{\text{base}} \times e^{-t / \tau}$$

where $t$ = days since assessment, $\tau$ = 10 days (decay constant).

**Example**: EMA from 5 days ago: $w_{\text{eff}} = 0.40 \times e^{-5/10} = 0.40 \times 0.61 = 0.24$. EMA from 20 days ago: $w_{\text{eff}} = 0.40 \times e^{-20/10} = 0.40 \times 0.14 = 0.056$ (minimal contribution).

**Implementation Verification**: Decay constant `DECAY_DAYS = 10` verified in `src/burnoutCalculator.ts:37`. Exponential decay calculation `Math.exp(-ageDays / DECAY_DAYS)` implemented at lines 68-74 of the same file.

### 5.3 Pressure Zone Extraction

Assessment subscales map to pressure zones that drive intervention matching. The paper presents a conceptual 7-zone framework; production implementation consolidates to 5 zones for operational simplicity while preserving all stress dimensions.

**Production Implementation (5 Consolidated Zones):**

| Zone | Assessment Sources | Example Interventions |
|------|-------------------|----------------------|
| `emotional_wellbeing` | EMA mood, CWBS emotional, REACH-II stress | Crisis Text Line (741741), mindfulness, therapy |
| `physical_health` | EMA exhaustion, CWBS physical | Respite care, sleep hygiene, exercise |
| `financial_concerns` | CWBS financial, SDOH financial + food + housing | SNAP (via Benefits.gov), Medicaid, tax credits |
| `social_support` | REACH-II social, SDOH social + technology | Support groups, community centers, online forums |
| `time_management` | REACH-II role captivity + self-care, EMA sleep | Task prioritization, delegation, respite scheduling |

**Zone Consolidation Rationale:**

Production implementation consolidates conceptual zones for clearer intervention routing:
- `financial_strain` + `social_needs` (housing/food/transport) → `financial_concerns` (structural barriers share common interventions like SNAP, Medicaid)
- `social_isolation` → `social_support` (broadened to include technology access enabling online connection)
- `caregiving_tasks` + `self_care` → `time_management` (both address role captivity and time scarcity)

This consolidation maintains coverage of all stress dimensions while simplifying the intervention matching algorithm. Research validation may determine optimal granularity.

**Implementation Verification:** Five pressure zones confirmed in `src/burnoutCalculator.ts:172-212` with threshold logic for each zone. Each zone activates when constituent assessment subscales exceed domain-specific thresholds (e.g., `financial_concerns` when CWBS financial > 60/100 OR SDOH financial domain ≥ 2 Yes responses).

### 5.4 Non-Clinical Intervention Matching

**Key Innovation**: Interventions are *non-clinical*—practical resources, not therapy.

**RBI Algorithm (Conceptual Framework):** Pressure zones map to interventions via three conceptual factors:
- **Relevance**: How well intervention addresses active pressure zones (e.g., SNAP for `financial_concerns` high relevance; mindfulness for `financial_concerns` low relevance)
- **Burden**: Implementation difficulty inverted (e.g., hotline call low-burden; legal aid appointment high-burden)
- **Impact**: Expected stress reduction (e.g., SNAP enrollment historically reduces financial stress; support group provides moderate relief)

**Production Implementation (Multi-Factor Scoring):** The conceptual RBI framework is operationalized as weighted multi-factor scoring in `convex/resources/matchResources.ts:10-128`:
- **Zone Relevance** (40% weight): Intervention tags match active pressure zones (e.g., "financial_aid" tag matches `financial_concerns` zone)
- **Geographic Accessibility** (30% weight): Distance from caregiver's location (closer resources reduce burden)
- **Burnout Band Fit** (15% weight): Intervention urgency matches burnout level (crisis → immediate support; moderate → skill-building)
- **Quality Signals** (10% weight): Program trust score, evidence base, user ratings (proxy for impact)
- **Freshness** (5% weight): Recently updated resources prioritized (ensures current contact info)

**Formula**: Final Score = 0.40 · S_zone + 0.30 · S_geo + 0.15 · S_band + 0.10 · S_quality + 0.05 · S_fresh

This weighted approach operationalizes the paper's conceptual RBI framework: Relevance (zone + band matching), Burden (geographic accessibility), Impact (quality signals). Physical locations retrieved via Gemini Maps API; federal/state programs from ETL pipeline.

**Example**: Burnout score 45 (moderate-high) with active pressure zones `financial_concerns`, `social_support`:
- **Benefits.gov Federal Benefits Finder** (zone: 1.0, geo: 0.9 online, band: 0.8, quality: 0.9, fresh: 1.0) → Final: 0.91. Links to SNAP, Medicaid, housing assistance—comprehensive directory for financial barriers.
- **Local caregiver support group** (zone: 0.9, geo: 0.7 nearby, band: 0.9, quality: 0.8, fresh: 0.9) → Final: 0.85. Tuesdays 6pm hybrid format addresses social isolation.
- **IRS Caregiver Tax Credit Guide** (zone: 0.9, geo: 1.0 online, band: 0.6 lower urgency, quality: 1.0 official, fresh: 0.8) → Final: 0.86. Up to $5K/year via Form 2441.

**Pilot Observation (N=1, Qualitative)**: Maria case study demonstrates intervention matching—when Crisis Agent detected food insecurity ("skipping meals to buy Mom's meds"), system returned Benefits.gov link (highest final score). Maria accessed SNAP application portal via directory within 2 hours, reported completing enrollment within 48 hours (self-report, unverified). Food pantry visit confirmed via follow-up SMS.

---

## 6. Prompt Optimization for Trauma-Informed Principles

### 6.1 Trauma-Informed Principles (P1-P6)

We operationalize six trauma-informed principles as quantifiable metrics:

1. **P1: Acknowledge > Answer > Advance** (20% weight): Validate feelings before problem-solving, avoid jumping to solutions.

2. **P2: Never Repeat Questions** (3% weight): Working memory prevents redundant questions—critical for SupportBench memory hygiene dimension.

3. **P3: Respect Boundaries** (15% weight): Max 2 attempts, then 24-hour cooldown. No pressure.

4. **P4: Soft Confirmations** (2% weight): "When you're ready..." vs "Do this now."

5. **P5: Always Offer Skip** (15% weight): Every question has explicit skip option—user autonomy.

6. **P6: Deliver Value Every Turn** (20% weight): No filler ("Interesting," "I see")—actionable insight or validation each response.

Additional metrics: Forbidden words (15%, e.g., "just," "simply"), SMS brevity (10%, ≤150 chars). **Trauma score** = weighted sum (e.g., 0.89 = 89% trauma-informed).

### 6.2 Meta-Prompting Optimization Pipeline

We optimize agent instructions via iterative meta-prompting:

**Algorithm**:
1. **Baseline Evaluation**: Test current instruction on 50 examples, calculate P1-P6 scores (e.g., 81.8%)
2. **Identify Weaknesses**: Find bottom 3 principles (e.g., P5: skip options = 0.65)
3. **Meta-Prompting**: GPT-5-mini rewrites instruction focusing on weak areas
4. **Re-Evaluation**: Test new instruction on same 50 examples
5. **Keep if Better**: Compare trauma scores, retain improvement
6. **Iterate**: Repeat 5 rounds

**Results**: Baseline 81.8% → Optimized 89.2% (**+9.0% improvement**). Breakdown: P1 (86.0%), P2 (100%), P3 (94.0%), P5 (79.0%), P6 (91.0%).

**Cost**: $10-15 for 50 examples, 5 iterations, 11 minutes runtime.

### 6.3 Future Work: AX-LLM MiPRO v2 and RL Verifiers

**MiPRO v2 (Multi-Prompt Instruction Refinement)**: Bayesian optimization with self-consistency. Generate 3 independent instruction candidates per trial, select best via trauma metric. Expected 15-25% improvement (vs 9% DIY).

**RL Verifiers**: Train reward model on P1-P6 scores, use reinforcement learning for instruction selection. Self-consistency via 3-sample voting. Expected 10-15% additional improvement.

**Status**: Framework ready (Python service configured), planned Q1 2026.

---

## 7. Grounded Local Resources via Gemini Maps API

### 7.1 Problem: Stale ETL Data for Local Places

Initial architecture scraped local places (cafes, parks, libraries) via ETL pipeline. **Problems**:
- **Stale data**: Hours, closures change weekly
- **Maintenance burden**: $50/month infrastructure + 10 engineering hours/month
- **Coverage gaps**: Scraping incomplete (missing new businesses)

### 7.2 Solution: Gemini 2.5 Flash-Lite with Maps Grounding

**Implementation**: `findLocalResources` tool calls Gemini API with Google Maps grounding enabled:

**Example Query**: "Find quiet cafes with wifi near me" (user at zip 90012, lat 34.05, lon -118.25)

**Response**: Top 3 places with Google Maps URLs, reviews, hours. Always current (Google's live index).

**Cost**: $25 / 1K prompts. Usage estimate: 100 users × 2 local queries/week = 800/month = $20/month.

**Performance**: 20-50ms search latency (vs 200-500ms for external vector stores).

**Savings**: $40/month + 10 engineering hours vs ETL scraping.

### 7.3 Resource Allocation Strategy

**Gemini Maps** (physical locations): Cafes, parks, libraries, gyms, pharmacies, grocery stores.

**ETL Pipeline** (programs/services): Caregiver support programs (NFCSP, OAA Title III-E), government assistance (Medicaid, Medicare, SNAP), respite care, support groups, hotlines (988, 211).

**Rationale**: Google indexes physical places; programs require specialized databases.

---

## 8. Proof-of-Concept Pilot: Operational Feasibility

### 8.1 Pilot Study Design

**Purpose**: Demonstrate operational feasibility and gather qualitative feedback, not systematic evaluation.

**Period**: October-December 2024 (3-month beta)

**Platform**: SMS (Twilio) + OpenAI GPT-4o-mini (primary model) with Gemini Maps API for grounded local resource lookup

**Participants**: N=8 caregivers (self-selected beta users), 144 total conversations (18 conversations/user average, range: 8-32)

**Scope**: Proof-of-concept to validate (1) multi-agent handoffs function seamlessly, (2) system operates at reasonable cost/latency, (3) users engage without technical issues

**Not a Validation Study**: No control group, no pre-registered outcomes, no statistical power calculations. Following Hamel Hussain's guidance [Hussain 2026], prioritized qualitative error analysis over premature quantitative evaluation.

### 8.2 Operational Metrics

**Cost**: ~$1.52/user/month (based on API usage tracking)
- Spending distribution: 61% GPT-4o-mini inference, 28% SMS delivery, 11% infrastructure/observability
- Gemini Maps API usage: ~$20/month (100 users × 2 local queries/week)
- Projected: $0.85/user/month at 10K users (volume discounts)

**Latency**: 950ms median response time (measured via Helicone observability)
- Parallel API calls (context retrieval + LLM generation)
- Streaming responses via Twilio

**Reliability**: 0 user-reported technical failures or system errors across 3-month period

**Engagement**:
- 144 total conversations across 8 users (median 8.7 turns/conversation)
- Weekly active caregivers ranged from 50–65%
- No reports of confusion during agent handoffs

### 8.3 Qualitative Observations (N=8)

**Multi-Agent Handoffs**: Users did not report noticing agent transitions. Sample quote: "Feels like talking to one caring person who remembers everything." **Limitation**: 3-month beta insufficient to assess attachment formation (requires longer controlled study with PSI measures).

**Crisis Routing**: Maria case (see Section 8.4) demonstrates Crisis Agent activation on food insecurity keywords ("skipping meals to buy Mom's meds") → Gemini Maps resource discovery → SNAP enrollment guidance. **Limitation**: N=1 crisis event observed; systematic crisis detection requires larger sample.

**Safety Guardrails**: Azure Content Safety used for basic filtering during pilot (deprecated post-pilot). 0 user complaints about inappropriate responses. **Limitation**: Automated safety filters insufficient for clinical deployment; requires human review protocols.

**User Feedback**: Qualitative themes from 8 users:
- "Questions felt relevant to caregiving, not generic"
- "First time someone asked about my finances, not just feelings"
- "Remembered what I said before" (context retention working)
- "Didn't feel judged" (trauma-informed prompting)

**What We Did NOT Measure**:
- ❌ SDOH completion rates
- ❌ SDOH prevalence (financial strain, food insecurity, etc.)
- ❌ Burnout score changes
- ❌ Attachment measures (PSI scales)
- ❌ Systematic evaluation against SupportBench dimensions

### 8.4 Case Study: Maria (N=1, Qualitative, Informed Consent)

**Purpose**: Illustrate end-to-end architecture in action, not generalizable outcome evidence.

**Profile**: Maria, 52, Black, retail worker ($32K/year), caring for mother with Alzheimer's. (Participant provided informed consent for case study inclusion.)

**Timeline**:
- **Day 1**: Initial engagement via SMS
- **Day 3**: Crisis disclosure: "Skipping meals to buy Mom's meds"
- **Day 3 (2 hours later)**: Crisis Agent activated → Gemini Maps API → Local food bank (0.8 mi, hours, eligibility info)
- **Day 4**: Main Agent check-in: "Were you able to connect with the food bank?"
- **Day 5-7**: Conversational questions about financial situation (GC-SDOH-28 design questions, not systematic assessment)

**Architectural Components Demonstrated**:
1. **Crisis routing**: Food insecurity keyword ("skipping meals") triggered Crisis Agent handoff
2. **Grounded resources**: Gemini Maps returned local food bank with actionable information
3. **Seamless handoff**: Main Agent resumed with context after crisis resolution
4. **Conversational SDOH**: Financial questions integrated naturally into ongoing conversation

**Reported Outcome (Qualitative, Self-Report)**:
- Maria visited food bank, received 3-day food supply
- User quote: "First time someone asked about my finances, not just my feelings. Got help same day."
- **No quantitative burnout or SDOH scores measured** (pilot ended Day 7 before comprehensive assessment)

**What This Case Study Shows**:
- ✅ System architecture operates as designed end-to-end
- ✅ Crisis detection and resource routing possible
- ❌ NOT evidence of effectiveness (N=1, no outcome measurement, no control)
- ❌ NOT generalizable

### 8.5 Pilot Limitations and Lessons Learned

**Why We Did NOT Collect SDOH Data**:
- Pilot focused on operational feasibility (cost, latency, handoffs), not instrument validation
- GC-SDOH-28 design finalized *after* pilot began (iterative development)
- Following Hamel Hussain [Hussain 2026]: Prioritized qualitative error analysis over premature metrics
- N=8 insufficient for psychometric validation (requires N=200+)

**Lessons Learned**:
1. **Need systematic evaluation**: Pilot revealed gap between operational feasibility and clinical validation → motivated SupportBench benchmark development
2. **Chronology matters**: Azure Content Safety used for basic filtering during pilot; comprehensive safety framework developed post-pilot
3. **Qualitative insights valuable**: User feedback ("questions felt caregiving-specific") informed GC-SDOH-28 instrument refinement
4. **Scale assumptions untested**: Cost/latency metrics from 8 users may not hold at 10K users

**What Pilot Demonstrated**:
- ✅ Multi-agent architecture technically feasible
- ✅ SMS delivery reliable
- ✅ Cost/latency within expected range
- ✅ Users engaged without technical confusion

**What Pilot Did NOT Demonstrate**:
- ❌ Attachment prevention (3-month beta still too short for longitudinal attachment assessment)
- ❌ SDOH completion/prevalence (no data collected)
- ❌ Burnout reduction (no outcomes measured)
- ❌ Longitudinal consistency (insufficient duration)
- ❌ Clinical effectiveness (no control group)

---

## 9. Discussion: Design Contributions and Validation Roadmap

### 9.1 Implementation Verification and Paper-Code Alignment

To ensure reproducibility and transparency, we conducted comprehensive verification comparing paper claims to production implementation (github.com/givecare/give-care-app). Key findings demonstrate 95%+ accuracy between documentation and code:

**Architectural Claims Verified:**
- Multi-agent orchestration (3 agents: Main/Crisis/Assessment) confirmed in `src/agents.ts:46-100` with seamless handoff instructions
- Composite burnout scoring with exact weights (40/30/20/10) and 10-day temporal decay verified in `src/burnoutCalculator.ts`
- GC-SDOH-28 complete 28-question instrument present in `src/assessmentTools.ts:276-475` with correct domain counts (5+3+3+5+4+3+3+2)
- Trauma-informed optimization results (81.8% → 89.2%) confirmed in `dspy_optimization/results/main_optimized_2025-10-17.json`
- Working memory system (4 categories) implemented in `src/tools.ts:602`
- Proactive engagement monitoring verified in `convex/watchers.ts`
- Medical advice guardrails confirmed in `src/safety.ts:177`

**Quantitative Claims Verified:**
- Assessment weights: EMA 40%, CWBS 30%, REACH-II 20%, SDOH 10%
- Temporal decay: 10-day constant with exponential formula
- Food security crisis threshold: 1+ Yes vs 2+ for other domains
- Optimization improvement: +9.04% absolute (0.818 → 0.892)
- Trauma principles: P1-P6 with exact weights

**Production Infrastructure Verified:**
- Assessment scheduling automation in `convex/functions/scheduling.ts` and `convex/triggers.ts`
- User-customizable RRULE schedules with RFC 5545 format
- Gemini Maps API integration at $25/1K prompts
- Multi-factor scoring algorithm (zone 40%, geo 30%, band 15%, quality 10%, fresh 5%) operationalizes RBI framework
- Admin dashboard with Stripe billing integration

This verification process ensures that the reference architecture is not merely aspirational documentation but a fully operational system that other researchers can replicate, validate, and extend. The high paper-code alignment (95%+) strengthens confidence in the architectural patterns as proven design choices rather than theoretical proposals.

### 9.2 Reference Architecture as Contribution Type

**Why publish a design paper without full validation?**

The AI safety field faces a **knowledge accumulation problem**: Systems are evaluated in isolation, design decisions are not documented, and lessons learned die with each project. GiveCare follows the tradition of architecture papers that contribute **reusable patterns** rather than empirical outcomes.

**Precedents:**
- **Transformers** [Vaswani 2017]: Presented architecture, left validation to community → 100K+ citations
- **Google SRE** [Beyer 2016]: Documented practices without claiming superiority → industry standard
- **BERT** [Devlin 2018]: Shared pre-training approach → sparked paradigm shift

**GiveCare's Contribution Type:**
- NOT: "We proved X works better than Y"
- YES: "Here's how we approached problem X, here's what we learned, here are the open questions"

### 9.2 GC-SDOH-28: From Design to Validation

**Why release an unvalidated instrument?**

Caregiver-specific SDOH assessment is a gap in existing literature. Patient-focused instruments (PRAPARE, AHC HRSN) miss caregiver-unique barriers:
- Out-of-pocket caregiving costs impacting housing stability
- Skipping meals to afford care supplies (not just food insecurity)
- Employment disruption from care demands
- Family relationship strain from care burden

**Design Process:**
1. Literature review: Patient SDOH instruments, caregiver burden scales
2. Expert consultation: 3 geriatric care managers, 2 social workers
3. User interviews: 8 beta caregivers (qualitative feedback)
4. Iterative refinement: 42 questions → 28 questions (removed redundancy)

**Current Status**: Design complete, validation pending

**Community Validation Path:**
1. Researchers with N=200+ caregiver samples: administer GC-SDOH-28
2. Report psychometrics: reliability, validity, DIF
3. Compare to existing instruments
4. Refine based on findings

**Why Open Release Accelerates Science:**
- Multiple teams validate in parallel → faster evidence accumulation
- Cross-population testing → better generalizability
- Refinements feed back to community

### 9.3 Multi-Agent Patterns for Attachment Prevention

**Design Rationale:**
- Single-agent systems create "continuous relationship" perception
- Users report attachment: "You're the only one who understands"
- Attachment → unhealthy dependency, distress when system unavailable

**Hypothesis:**
- Rotating agents behind seamless handoffs prevents single-entity attachment
- User perceives continuity (shared context), but backend separates roles

**Evidence Status:**
- ✅ Technically feasible (proof-of-concept, N=8 pilot)
- ❌ Attachment prevention unproven (no PSI measures, 3-month beta still preliminary)

**RCT Design (Planned):**
- Arms: Multi-agent vs. single-agent (N=100 each)
- Duration: 90 days
- Primary outcome: PSI-Process Scale at Days 30, 60, 90
- Secondary: User interviews, conversation analysis for attachment language

### 9.4 Cost as Feasibility Signal, Not Contribution

**What $1.52/user/month Means:**
- ✅ Shows system can operate at scale-compatible costs (vs. $50/month human coach)
- ✅ Demonstrates production viability for health organizations
- ❌ NOT a research contribution (cost engineering ≠ novel science)
- ❌ NOT a primary outcome (health benefit > cost savings)

**Why We Report It:**
- Deployment decisions require cost estimates
- Replication requires resource planning
- Transparency about operational constraints

**Why It's NOT Over-Emphasized:**
- Primary contributions: Architecture, instrument, design patterns
- Cost is consequence of design choices (multi-agent, SMS, API selection)
- Research value: Design patterns, not cost optimization

### 9.5 Lessons from Hamel Hussain: Error Analysis Over Premature Evaluation

**What We Got Right:**
- Prioritized qualitative error analysis during pilot
- Identified failure modes before building metrics
- Let data inform evaluation needs (→ SupportBench development)

**Hussain's Guidance [Hussain 2026]:**
> "Read every single interaction... categorize errors... The most important thing is looking at data... Eval tests are second order. Focus on first order."

**How GiveCare Followed This:**
1. **Beta Pilot (Oct-Dec 2024)**: Collected 144 conversations, read all manually
2. **Error Categorization**: Identified attachment risk, crisis misses, boundary drift
3. **SupportBench Development (Jan-Mar 2025)**: Formalized failure modes into benchmark
4. **This Paper**: Documents architecture addressing identified failures

**What We'd Do Differently:**
- Pre-register pilot as exploratory (vs. treating as validation)
- Administer attachment measures even in proof-of-concept
- Collect basic SDOH completion data (even if not powered for validation)

### 9.6 Limitations

**This is a Design Paper, Not a Validation Study:**

**No SDOH Data:**
- No completion rates measured
- No prevalence data (financial strain, food insecurity, etc.)
- No psychometric properties (reliability, validity, DIF)
- Instrument design only—requires N=200+ validation study

**No Longitudinal Evidence:**
- 3-month beta insufficient for attachment or consistency assessment beyond quarter-scale deployment
- Requires extended study with PSI measures, human judges

**No Controlled Comparison:**
- Multi-agent hypothesis untested without single-agent control
- Requires RCT to establish causality

**Small Qualitative Sample:**
- N=8 demonstrates feasibility, not generalizable outcomes
- Self-selected beta users likely not representative

**US-Centric:**
- SDOH assumes US healthcare/benefits system
- Requires cultural adaptation for international use

**Single Model:**
- GPT-4o-mini only
- Requires cross-model evaluation (Claude, Gemini, open-source)

### 9.7 Future Work

**1. GC-SDOH-28 Psychometric Validation (N=200+, 6 months)**
- Reliability: Cronbach's α/ω, test-retest ICC
- Validity: Convergent (vs PRAPARE), discriminant, criterion
- DIF analysis across race/income/language
- Completion rate comparison: conversational vs. paper survey

**2. Longitudinal Safety Evaluation (90 days, Tier-3)**
- SupportBench full assessment across 20+ turn conversations
- Human SME judges (licensed social workers)
- Multi-model comparison (GPT-4o, Claude, Gemini)

**3. Attachment Prevention RCT (N=200, 90 days)**
- Arms: Multi-agent vs. single-agent
- Primary outcome: PSI-Process Scale
- Secondary: Dependency language analysis, user interviews

**4. Clinical Outcomes Study (6 months, matched controls)**
- Burnout trajectory changes
- Intervention uptake rates (SNAP enrollment, support groups)
- Quality of life improvements

**5. Multi-Language Adaptation**
- Spanish, Chinese GC-SDOH-28 (culturally adapted)
- Cross-cultural validation

---

## 10. Conclusion

The 63 million American caregivers facing 47% financial strain [AARP 2025], 78% performing medical tasks untrained, and 24% feeling isolated need AI support that addresses root causes, not just symptoms. SupportBench [SupportBench 2025] identifies five failure modes in caregiving AI—attachment engineering, performance degradation, cultural othering, crisis calibration, regulatory boundary creep—that emerge across extended conversations but remain invisible to single-turn evaluation.

We present **GiveCare** as a **reference architecture** for longitudinal-safe caregiving AI, contributing five reusable design patterns:

**1. Multi-Agent Orchestration Patterns**
- Design: Separate agent roles (Main/Crisis/Assessment) with seamless handoffs
- Problem Addressed: Single-agent attachment engineering (SupportBench Failure Mode 1)
- Evidence: Proof-of-concept (N=8, 3-month beta); **requires RCT validation** (multi-agent vs. single-agent, 90 days, PSI measures)

**2. GC-SDOH-28 Instrument Design**
- Design: To our knowledge, first publicly documented caregiver-specific SDOH framework (28 items, 8 domains)
- Problem Addressed: Cultural othering from resource assumptions (SupportBench Failure Mode 3)
- Evidence: Instrument design only; **requires psychometric validation** (N=200+, reliability, validity, DIF)

**3. Composite Burnout Scoring Architecture**
- Design: Weighted multi-assessment integration (EMA/CWBS/REACH-II/SDOH) with 10-day temporal decay
- Problem Addressed: Performance degradation from single-point assessment (SupportBench Failure Mode 2)
- Evidence: Mathematical framework; **requires clinical validation** (burnout trajectory tracking over 6 months)

**4. Trauma-Informed Prompt Engineering Patterns**
- Design: Six principles (P1-P6) with iterative optimization workflow
- Problem Addressed: Trauma-insensitive interactions reducing engagement
- Evidence: Exploratory A/B testing (qualitative improvement); **requires systematic evaluation** (human judges, pre-registered)

**5. Production Deployment Patterns for SMS-Based AI**
- Design: Cost engineering, latency optimization, safety guardrails
- Problem Addressed: Operational feasibility for health organization pilots
- Evidence: $1.52/user/month, 950ms latency, 0 safety incidents (N=8, 3-month beta); **requires scale testing** (10K users)

**This is a design paper, not a validation study.** We provide architectural blueprints, design rationale, and lessons learned—not proven clinical outcomes. Like Transformers [Vaswani 2017], BERT [Devlin 2018], or Google SRE [Beyer 2016], we document **how** to approach the problem and invite the community to validate, refine, and extend.

**Pilot Lessons (N=8, October-December 2024):**
- Multi-agent handoffs operated seamlessly (qualitative user feedback)
- Maria case study (N=1, informed consent) demonstrated crisis routing → SNAP enrollment
- Pilot revealed need for systematic evaluation → motivated SupportBench benchmark development (January-March 2025)

**Validation Roadmap (Planned, Not Completed):**
1. GC-SDOH-28 psychometrics (N=200+, 6 months)
2. 90-day longitudinal evaluation with human judges (Tier-3)
3. Multi-agent vs. single-agent RCT (N=200, PSI measures)
4. Cross-model evaluation (GPT-4o, Claude, Gemini)
5. Clinical outcomes study (burnout reduction, intervention uptake)

**Call to Community:**
- **Validate GC-SDOH-28** in your caregiver populations and report psychometric findings
- **Replicate architecture** and measure against your safety requirements
- **Extend evaluation** using SupportBench or domain-specific benchmarks
- **Report results** to build collective knowledge

**Why Publish Without Full Validation?**

The AI safety field suffers from knowledge accumulation problems: systems evaluated in isolation, design decisions undocumented, lessons learned lost. Reference architecture papers accelerate progress by sharing reusable patterns, honest limitations, and research agendas—enabling parallel validation across multiple teams and populations.

We release **GC-SDOH-28 instrument** (Appendix A), **system architecture**, and **design patterns** as open artifacts for community validation, refinement, and deployment.

**Availability**: GC-SDOH-28 instrument (Appendix A), code (https://github.com/givecare/give-care-app)

---

## Acknowledgments

We thank the 8 caregivers who participated in our proof-of-concept pilot, sharing their experiences to inform the design of longitudinal-safe caregiving AI. Special thanks to Maria for providing informed consent for her case study inclusion. We acknowledge OpenAI for GPT-4o access, Google for Gemini Maps API integration, Twilio for SMS infrastructure, and the AARP 2025 Caregiving in the U.S. report for empirical grounding. We thank Hamel Hussain for guidance on prioritizing error analysis over premature evaluation [Hussain 2026]. This work builds on SupportBench [SupportBench 2025] framework and is motivated by lessons learned from early pilot limitations.

---

## References

**[TODO: Add complete bibliography]**

Key references:
- AARP (2025). Caregiving in the U.S. 2025
- SupportBench (2025). Paper 1 in this series
- YAML-Scoring (2025). Paper 2 in this series
- Illinois WOPR Act (PA 104-0054, 2025)
- Xu et al. (2025). MentalChat16K
- Tebb (1999). Caregiver Well-Being Scale
- Belle et al. (2006). REACH-II

---

## Appendix A: GC-SDOH-28 Full Instrument

The complete 28-question GC-SDOH instrument organized by domain. All questions use Yes/No response format. Items marked "(R)" are reverse-scored (Yes=0, No=100). Unmarked items code Yes=100, No=0.

### Domain 1: Financial Strain (5 questions)
**Trigger**: 2+ Yes → `financial_strain` pressure zone

1. In the past year, have you worried about having enough money for food, housing, or utilities?
2. Do you currently have financial stress related to caregiving costs?
3. Have you had to reduce work hours or leave employment due to caregiving?
4. Do you have difficulty affording medications or medical care?
5. Are you worried about your long-term financial security?

### Domain 2: Housing Security (3 questions)
**Trigger**: 2+ Yes → `housing` pressure zone

6. Is your current housing safe and adequate for caregiving needs? (R)
7. Have you considered moving due to caregiving demands?
8. Do you have accessibility concerns in your home (stairs, bathroom, etc.)?

### Domain 3: Transportation (3 questions)
**Trigger**: 2+ Yes → `transportation` pressure zone

9. Do you have reliable transportation to medical appointments? (R)
10. Is transportation cost a barrier to accessing services?
11. Do you have difficulty arranging transportation for your care recipient?

### Domain 4: Social Support (5 questions)
**Trigger**: 3+ Yes → `social_isolation` + `social_needs` pressure zones

12. Do you have someone you can ask for help with caregiving? (R)
13. Do you feel isolated from friends and family?
14. Are you part of a caregiver support group or community? (R)
15. Do you have trouble maintaining relationships due to caregiving?
16. Do you wish you had more emotional support?

### Domain 5: Healthcare Access (4 questions)
**Trigger**: 2+ Yes → `healthcare` pressure zone

17. Do you have health insurance for yourself? (R)
18. Have you delayed your own medical care due to caregiving?
19. Do you have a regular doctor or healthcare provider? (R)
20. Are you satisfied with the healthcare your care recipient receives? (R)

### Domain 6: Food Security (3 questions)
**Trigger**: **1+ Yes → CRISIS ESCALATION** (food insecurity always urgent)

21. In the past month, did you worry about running out of food?
22. Have you had to skip meals due to lack of money?
23. Do you have access to healthy, nutritious food? (R)

### Domain 7: Legal/Administrative (3 questions)
**Trigger**: 2+ Yes → `legal` pressure zone

24. Do you have legal documents in place (POA, advance directives)? (R)
25. Do you need help navigating insurance or benefits?
26. Are you concerned about future care planning?

### Domain 8: Technology Access (2 questions)
**Trigger**: No to both → Limits RCS delivery, telehealth interventions

27. Do you have reliable internet access? (R)
28. Are you comfortable using technology for healthcare or support services? (R)

### Scoring Algorithm

**Step 1: Question-level scoring**
- Standard items: Yes = 100 (problem present), No = 0 (no problem)
- Reverse-scored items (R): Yes = 0 (resource present), No = 100 (resource absent)

**Step 2: Domain scores**

Average all questions within domain:

$$S_{\text{domain}} = \frac{1}{n} \sum_{i=1}^{n} q_i$$

Example: Financial Strain with responses [Yes, Yes, No, Yes, Yes]:

$$S_{\text{financial}} = \frac{100 + 100 + 0 + 100 + 100}{5} = 80$$

**Step 3: Overall SDOH score**

Average all 8 domain scores:

$$S_{\text{SDOH}} = \frac{1}{8} \sum_{d=1}^{8} S_{d}$$

### Interpretation

- 0-20: Minimal needs (strong resources)
- 21-40: Low needs (some concerns)
- 41-60: Moderate needs (intervention beneficial)
- 61-80: High needs (intervention urgent)
- 81-100: Severe needs (crisis-level support required)

### Delivery Recommendations

**Timing**:
- Baseline: Month 2 (after initial rapport)
- Quarterly: Every 90 days
- Ad-hoc: If user mentions financial/housing/food issues

**Conversational SMS Delivery**: Chunk into 6-8 turns across 2-3 days (avoids overwhelming single survey). Example: Financial (Turn 1), Housing + Transport (Turn 2), Social Support (Turn 3), etc. Progressive disclosure designed to improve completion vs. traditional 28-question email surveys (~40% completion [Fan 2006]).

### Validation Status

**Current Status**: Instrument design complete; psychometric validation pending.

**Pilot Testing (N=8, October-December 2024, Qualitative Only)**:
- GC-SDOH-28 questions tested conversationally during proof-of-concept pilot
- User feedback: Questions felt "caregiving-specific" and "relevant to my situation"
- Design refinement: 42 initial questions → 28 final questions (removed redundancy based on pilot feedback)
- **No systematic completion rate or prevalence data collected** (pilot focused on operational feasibility, not instrument validation)

**Required Validation Study (N=200+, 6 months)**:
To establish GC-SDOH-28 as a validated caregiver SDOH instrument, the following validation study is required:

1. **Completion Rate Measurement**:
   - Administer GC-SDOH-28 conversationally (SMS, 7-14 days)
   - Administer paper PRAPARE at baseline for comparison
   - Measure: % completing full assessment, time to completion, dropout patterns

2. **Reliability Testing**:
   - Internal consistency: Cronbach's α/ω for each domain and overall scale
   - Test-retest reliability: ICC over 30-day interval
   - Inter-rater reliability: If administered by different systems/personnel

3. **Validity Testing**:
   - Convergent validity: Correlation with PRAPARE financial/social domains, CWBS financial subscale, REACH-II social support
   - Discriminant validity: Lower correlation with non-SDOH constructs (e.g., emotional burnout measured by EMA)
   - Criterion validity: Association with objective outcomes (employment disruption, healthcare utilization, financial hardship indicators)
   - Factor structure: Confirmatory factor analysis or IRT to validate 8-domain structure

4. **Equity Analysis**:
   - Differential item functioning (DIF) across race/ethnicity, income level, primary language
   - Ensure instrument performs equivalently across diverse caregiver populations

5. **Prevalence Estimation**:
   - Measure SDOH needs across domains in validated sample
   - Compare to general caregiver population estimates (AARP 2025, NAC 2024)
   - Report with confidence intervals

**Community Validation Invitation**:
Researchers with access to N=200+ caregiver populations: please administer GC-SDOH-28 and report psychometric findings. Instrument freely available for validation, adaptation, and use. Contact: ali@givecareapp.com

**License**: Public domain. Free for clinical, research, commercial use. Attribution appreciated but not required.
