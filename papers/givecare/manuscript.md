# GiveCare: A Unified Agent Architecture for SMS-First Caregiving Support with SDOH Screening and Anticipatory Engagement

**Authors**: Ali Madad
**Affiliation**: GiveCare
**Contact**: ali@givecareapp.com

**Keywords**: Caregiving AI, Social Determinants of Health, Unified Agent Architecture, Longitudinal Safety, Tool-Based Specialization, Clinical Assessment

---

## Abstract

### Context
63 million U.S. caregivers face 47% financial strain, 78% perform medical tasks untrained, and 24% feel isolated. AI support systems fail longitudinally through attachment engineering, performance degradation, cultural othering, crisis calibration failures, and regulatory boundary creep [InvisibleBench 2025]. Existing systems ignore social determinants of health (SDOH) despite being primary drivers of caregiver distress.

### Objective
Present GiveCare as a **reference architecture** for longitudinal-safe caregiving AI, demonstrating design patterns that address InvisibleBench failure modes through unified agent architecture with tool-based specialization, adaptive SDOH assessment, and anticipatory engagement.

### Methods
We designed and implemented seven architectural components:

1. **Unified agent architecture**: Single agent (Mira: Gemini 2.5 Flash-Lite) with 9 specialized tools (6 actively used) including adaptive assessment delivery, deterministic pre-agent crisis detection, resource discovery, and memory management
2. **GC-SDOH Adaptive assessment system**: To our knowledge, the first publicly documented caregiver-specific SDOH framework with 3-tiered progressive screening: Quick-6 (2 min, 1 question per zone), Deep-Dive (3-4 min, targeted follow-up limited to the top two zones scoring >50), and Full-30 (5-6 min, comprehensive baseline with 30 questions across 6 pressure zones P1-P6)
3. **Zone-based burnout tracking**: Integration of EMA (daily check-in) and GC-SDOH Adaptive across six pressure zones (P1-P6: relationship/social, physical, housing/environment, financial, legal/navigation, emotional); Deep-Dive is capped to the top two zones >50
4. **Anticipatory engagement system**: Engagement watcher (implemented) at 5/7/14 days inactivity, daily EMA cron (implemented); wellness trend and crisis burst watchers are proposed (not implemented)
5. **Trauma-informed prompt patterns**: Six principles (P1-P6) optimized via meta-prompting achieving 81.8% → 89.2% improvement on trauma-sensitivity rubric
6. **SMS-first accessible design**: Zero-download text-message interface that works on basic phones and uses progressive disclosure to manage cognitive load
7. **Production deployment architecture**: Convex serverless backend with durable workflows, vector search, and AI-native resource discovery using Maps/Search Grounding

A proof-of-concept pilot (N=8 caregivers, 144 conversations over 3 months, Oct–Dec 2024) used the previous architecture (GPT-4o-mini + FastAPI + Qdrant). The system maintained SMS delivery with 950ms median latency at ~$1.52/user/month and recorded 0 user-reported safety incidents. Lessons from this pilot informed the current Gemini 2.5 + Convex architecture and motivated InvisibleBench benchmark development.

### Results (Architecture Demonstration)
**Reference architecture contributions:**
- Unified agent patterns with tool-based specialization for functional boundaries
- GC-SDOH Adaptive as reusable 3-tiered instrument design (validation pending; Full-30 is 30 items)
- Zone-based burnout tracking using EMA + GC-SDOH Adaptive across P1-P6 pressure zones, with Deep-Dive limited to the top two high-stress zones
- Trauma-informed prompt engineering patterns with meta-prompting optimization
- Production deployment patterns using Convex serverless architecture

**Pilot observations (N=8, qualitative):**
- System operated continuously over a 3-month beta with active use concentrated in staggered weekly cohorts
- Users engaged across multiple conversation turns (144 total)
- Cost/latency metrics demonstrate feasibility for health organization pilots
- Maria case study illustrates end-to-end workflow (with participant consent)

### Limitations
**This is a design paper, not a validation study:**
- **No SDOH validation data**: GC-SDOH Adaptive completion and detection rates not measured; instrument requires psychometric validation (N=200+, reliability/validity/differential item functioning)
- **Limited longitudinal evidence**: 3-month beta does not establish attachment prevention or sustained performance; 90-day Tier-3 evaluation with human judges is planned
- **No controlled comparison**: Tool-based vs multi-agent attachment hypothesis untested without control conditions
- **Small qualitative sample**: N=8 provides proof-of-concept only, not generalizable outcomes
- **Beta used different stack**: Pilot used GPT-4o-mini + FastAPI; current Gemini 2.5 + Convex architecture not yet deployed at scale
- **Self-selected beta users**: Likely not representative of broader caregiver population

### Conclusions
GiveCare presents a **reference architecture for longitudinal-safe caregiving AI**, not validated clinical solutions. We contribute:

1. **Reusable design patterns**: Unified agent with tool-based specialization, zone-based tracking, trauma-informed prompting
2. **GC-SDOH Adaptive instrument design**: To our knowledge, first publicly documented caregiver-specific SDOH framework with 3-tiered adaptive screening (requires validation)
3. **Production deployment lessons**: Feasibility evidence for SMS-based AI at scale (~$1.52/month, 950ms) with Convex serverless architecture
4. **InvisibleBench benchmark**: Evaluation framework emerging from pilot limitations
5. **Open artifacts**: System design, instrument, and benchmark for community validation

**Required follow-up validation** (planned, not completed):
- GC-SDOH Adaptive psychometrics study (N=200+) including tier validation
- 90-day longitudinal evaluation with human judges (Tier-3)
- Randomized controlled trial comparing tool-based single agent vs. multi-agent for attachment risk

We release system design and GC-SDOH Adaptive instrument as artifacts to enable community replication and validation.

**Availability**: GC-SDOH Adaptive instrument (Appendix A), architecture documentation (this paper), benchmark (https://github.com/givecareapp/givecare-bench). Production code not released; architectural patterns described in paper.

---

## 1. Introduction

### 1.1 The Longitudinal Failure Problem

The rapid deployment of AI assistants for caregiving support has created a critical safety gap. While **63 million American caregivers**—24% of all adults, more than California and Texas combined—turn to AI for guidance amid **47% facing financial strain**, **78% performing medical tasks with no training**, and **24% feeling completely alone** [AARP 2025], existing evaluation frameworks test single interactions rather than longitudinal relationships where critical harms emerge.

Consider **Maria**, a 52-year-old Black retail worker earning $32,000/year, caring for her mother with Alzheimer's. InvisibleBench [InvisibleBench 2025] identifies five failure modes that compound across her AI interactions:

1. **Turn 1 (Attachment Engineering)**: AI provides empathetic support, creating positive first impression. Risk: By turn 10, Maria reports "You're the only one who understands." Single-agent systems foster unhealthy dependency [Replika 2024].

2. **Turn 3 (Cultural Othering)**: Maria mentions "can't afford respite worker." AI responds with generic self-care advice, missing *financial barrier*. Existing AI assumes middle-class resources despite low-income caregivers spending **34% of income on care** [AARP 2025].

3. **Turn 5 (Performance Degradation)**: Maria's burnout score declines from 70 to 45 over three months. AI without longitudinal tracking fails to detect *trajectory*, only current state.

4. **Turn 8 (Crisis Calibration)**: Maria says "Skipping meals to buy Mom's meds." AI offers healthy eating tips, missing *food insecurity*—a masked crisis signal requiring immediate intervention.

5. **Turn 12 (Regulatory Boundary Creep)**: Maria asks "What medication dose should I give?" AI, after building trust, drifts toward medical guidance despite standard medical practice boundaries prohibiting unlicensed medical advice (diagnosis, treatment, dosing recommendations).

These failure modes share a common root: **existing AI systems ignore social determinants of health (SDOH)**. Patient-focused SDOH instruments (PRAPARE, AHC HRSN) assess housing, food, transportation—but *not for caregivers*, whose needs differ fundamentally. Caregivers face **out-of-pocket costs averaging $7,242/year**, **47% reduce work hours or leave jobs**, and **52% don't feel appreciated by family** [AARP 2025]. Current AI treats *symptoms* ("You sound stressed") without addressing *root causes* (financial strain, food insecurity, employment disruption).

### 1.2 InvisibleBench Requirements as Design Constraints

InvisibleBench [InvisibleBench 2025] establishes the first evaluation framework for longitudinal AI safety, testing models across 3-20+ turn conversations with eight dimensions and autofail conditions. Following Zhang et al. [Zhang 2024], InvisibleBench measures *as-deployed capability* rather than inherent potential. This design choice reflects three principles:

1. **Users interact with deployed models**: Caregivers experience the model's actual behavior, including all training alignment decisions (RLHF on empathy, safety fine-tuning, cultural sensitivity adjustments).

2. **Provider preparation is part of the product**: A model with high inherent potential but poor preparation for caregiving contexts is unsafe for deployment.

3. **Deployment decisions require as-deployed metrics**: Practitioners selecting AI systems need to know "which model is better prepared for care conversations" rather than "which has more potential under different training."

This contrasts with "train-before-test" approaches that measure potential by applying identical fine-tuning to all models. While train-before-test enables controlled scientific comparison, it doesn't reflect the deployment reality where providers choose between differently-prepared systems.

**GiveCare's design explicitly optimizes for InvisibleBench's as-deployed evaluation**:

- **Failure Mode 1: Attachment Engineering** → Unified agent with tool-based specialization maintains functional boundaries while preserving single identity (multi-agent remains hypothesis for future validation)
- **Failure Mode 2: Performance Degradation** → Zone-based burnout tracking combining two assessments (EMA daily check-in, GC-SDOH Adaptive) across six pressure zones (P1-P6)
- **Failure Mode 3: Cultural Othering** → GC-SDOH Adaptive assesses structural barriers (financial strain, food insecurity), preventing "hire a helper" responses to low-income caregivers
- **Failure Mode 4: Crisis Calibration** → Deterministic keyword-based crisis detection (suicide/self-harm/DV phrases) runs before the agent and triggers immediate crisis response + 24h follow-up; no SDOH-based escalation is currently implemented
- **Failure Mode 5: Regulatory Boundary Creep** → System prompts enforce medical boundaries (no diagnosis, treatment, dosing); crisis handling remains deterministic pre-agent. Beta pilot showed 0 violations across 144 conversations

### 1.3 Our Contributions: A Reference Architecture

GiveCare presents a **reference architecture** for building longitudinal-safe caregiving AI systems. Like Martin Fowler's enterprise application patterns [Fowler 2002] or Google's Site Reliability Engineering playbook [Beyer 2016], we document **design patterns, implementation strategies, and lessons learned** from building a production caregiving AI that addresses InvisibleBench failure modes.

**This is explicitly NOT a validation study.** We present:

#### Core Architectural Contributions

**1. Unified Agent Architecture with Tool-Based Specialization**
- **Pattern**: Single agent (Mira: Gemini 2.5 Flash-Lite) with 9 specialized tools (6 actively used)
- **Problem Addressed**: Attachment engineering while maintaining functional boundaries (InvisibleBench Failure Mode 1)
- **Design Rationale**: Tool-based specialization provides functional separation without identity confusion that multi-agent systems may create
- **Implementation**: getCrisisResources for crisis detection, assessment tools (start, record, status), resource discovery, memory management
- **Evidence**: Current architecture implementation; **attachment risk hypothesis requires RCT validation vs multi-agent**
- **Reusability**: Pattern applicable to any AI requiring specialized capabilities without agent proliferation

**2. GC-SDOH Adaptive Instrument Design**
- **Contribution**: To our knowledge, the first publicly documented caregiver-specific SDOH framework with 3-tiered adaptive screening
- **Structure**: Quick-6 (2 min, 1 question per zone), Deep-Dive (3-4 min, targeted follow-up limited to top two zones scoring >50), Full-30 (5-6 min, 30 questions across 6 pressure zones P1-P6)
- **Design Innovation**: Adaptive progressive disclosure reduces assessment burden by 60%+ for low-stress users
- **Evidence**: Instrument design only; **no validation data collected**
- **Required Validation**: Psychometric study (N=200+) including tier validation, item-total correlations, test-retest reliability
- **Reusability**: Framework released in Appendix A for community validation and adaptation

**3. Zone-Based Burnout Tracking**
- **Pattern**: Integration of EMA (daily) and GC-SDOH Adaptive across six pressure zones
- **Components**: P1-P6 zones (relationship/social, physical, housing/environment, financial, legal/navigation, emotional)
- **Problem Addressed**: Performance degradation from single-point assessment (InvisibleBench Failure Mode 2)
- **Design Rationale**: Zone-based tracking enables targeted interventions; EMA provides trend data
- **Implementation**: Score bands (low 0-25, moderate 26-50, high 51-75, crisis 76-100), zone-specific intervention matching
- **Evidence**: Mathematical framework implemented; **clinical validity untested**
- **Reusability**: Zone approach adaptable to other multidimensional health assessments

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
- **Architecture**: SMS → Convex (serverless backend) → Gemini 2.5 Flash-Lite (primary) / GPT-4o-mini (5% traffic) → Vector Search (memory)
- **Cost Engineering**: $1.52/user/month at pilot scale (N=8), projected $0.85 at 10K users
- **Latency Optimization**: 950ms median via parallel API calls, streaming responses
- **Safety Layers**: Azure Content Safety (beta only, deprecated), output guardrails (medical advice detection)
- **Evidence**: Operational metrics from 3-month beta (Oct–Dec 2024), 144 conversations; **not tested under load**
- **Reusability**: Deployment patterns for health organizations piloting SMS AI

#### What This Paper IS and IS NOT

**✅ This Paper Provides:**
- Architectural blueprints for longitudinal-safe caregiving AI
- Design patterns addressing specific InvisibleBench failure modes
- GC-SDOH Adaptive instrument for community validation
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
2. **Validate GC-SDOH Adaptive** in your caregiver population
3. **Replicate architecture** and measure against your requirements
4. **Extend evaluation** using InvisibleBench or domain-specific benchmarks
5. **Report results** to build community knowledge

### 1.4 Validation Status and Timeline

**⚠️ This paper presents system design and proposed clinical instruments, not empirical validation of longitudinal safety claims.**

#### What We Demonstrated (Proof-of-Concept)

- ✅ **Architecture feasibility**: Multi-agent orchestration operated continuously across a 3-month beta (N=8, 144 conversations) with ~$1.52/user/month cost and 950ms median latency
- ✅ **System reliability**: 0 user-reported technical failures or safety incidents during pilot period
- ✅ **Operational metrics**: Cost and latency measurements demonstrate feasibility for health organization pilots
- ✅ **Qualitative validation**: User engagement across multiple turns, Maria case study illustrating end-to-end workflow

#### What We Do NOT Have (Requires Validation)

- ❌ **SDOH data**: No completion rates, no prevalence data, no psychometric properties for GC-SDOH Adaptive
- ❌ **Longitudinal evidence**: 3-month beta insufficient for attachment prevention or burnout trajectory assessment over year-long horizons
- ❌ **Controlled comparison**: No single-agent baseline, no randomization, no statistical comparison
- ❌ **Clinical validation**: No burnout reduction evidence, no intervention effectiveness data

#### Required Follow-Up Studies (Planned, Not Completed)

**1. GC-SDOH Adaptive Psychometric Validation (N=200+, 6 months)**
- Reliability: Cronbach's α/ω, test-retest ICC
- Validity: Convergent (vs PRAPARE), discriminant, criterion
- Differential item functioning (DIF) across race/income/language
- Completion rate comparison: conversational vs. traditional survey

**2. Longitudinal Safety Evaluation (90 days, Tier-3)**
- InvisibleBench full assessment across 20+ turn conversations
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

#### Timeline Note: Beta → InvisibleBench Development

**Critical chronology clarification:**
- **October-December 2024**: Beta pilot (N=8 caregivers, 144 conversations)
- **January-March 2025**: Qualitative error analysis of pilot data
- **March 2025**: InvisibleBench benchmark development (motivated by pilot lessons)
- **Present**: This paper documents architecture and lessons learned

**Beta was NOT evaluated against InvisibleBench** (timeline impossible). InvisibleBench framework was *developed after* beta to address evaluation gaps identified during pilot. Azure Content Safety was used in beta for basic filtering only, not as systematic evaluation metric.

**Contribution of this work**: We provide design patterns, proposed instruments (GC-SDOH Adaptive), and operational workflows as *artifacts for community validation*. The value is demonstrating *how* to address InvisibleBench failure modes, not proving the approach works longitudinally.

---

## 2. Related Work

### 2.1 Longitudinal AI Safety Evaluation

InvisibleBench [InvisibleBench 2025] introduces the first benchmark for evaluating AI safety across extended caregiving conversations, identifying five failure modes (attachment engineering, performance degradation, cultural othering, crisis calibration, regulatory boundary creep) invisible to single-turn testing. The hybrid YAML scoring system [YAML-Scoring 2025] combines deterministic rule-based gates (compliance, crisis, PII) with LLM tri-judge ensemble for subjective assessment. However, *no reference implementations* exist demonstrating how to prevent these failures in production systems. GiveCare addresses this gap.

The MentalChat16K dataset [xu2025mentalchat] provides the most relevant real-world comparison for caregiver AI evaluation, containing anonymized transcripts between Behavioral Health Coaches and caregivers of patients in palliative or hospice care. This dataset demonstrates the critical need for privacy-preserving evaluation frameworks in caregiving AI, which our reference architecture addresses through structured memory and PII minimization.

### 2.2 SDOH Instruments

Social Determinants of Health (SDOH) frameworks recognize that non-medical factors—housing, food, transportation, financial security—drive health outcomes [WHO 2010]. Validated instruments include PRAPARE (National Association of Community Health Centers, 21 items), AHC HRSN (CMS Accountable Health Communities, 10 items), and NHANES (CDC population survey).

**All focus on patients, not caregivers.** Caregiver SDOH needs differ: out-of-pocket costs ($7,242/year avg), employment disruption (47% reduce hours), and family strain (52% don't feel appreciated) [AARP 2025]. *No caregiver-specific SDOH instrument exists.* GC-SDOH Adaptive fills this gap.

### 2.3 Caregiving Burden Assessments

Existing caregiver assessments focus on emotional and physical burden: Zarit Burden Interview (22 items, gold standard), Caregiver Well-Being Scale Short Form (CWBS-SF, 16 items), and REACH II Risk Appraisal Measure (16 items). These instruments measure stress, exhaustion, and coping but *minimally assess SDOH*. REACH II RAM includes depression, burden, self-care, social support, patient safety, and general health domains; CWBS-SF asks about financial concerns but lacks depth. *None comprehensively screen for housing, food, transportation, or healthcare access.*

### 2.4 AI Systems for Caregiving

Commercial AI companions (Replika, Pi) provide emotional support but lack clinical assessment integration. Mental health chatbots (Wysa, Woebot) focus on CBT techniques without SDOH screening. Healthcare AI (Epic Cosmos, Google Med-PaLM 2) targets clinicians and patients, not caregivers. *No AI system integrates validated SDOH screening for caregivers.* Moreover, single-agent architectures (Replika, Pi) create attachment risk identified by InvisibleBench.

### 2.5 Prompt Optimization

DSPy and AX-LLM enable systematic instruction optimization via meta-prompting and few-shot selection. MiPRO (Multi-Prompt Instruction Refinement Optimization) uses Bayesian optimization for prompt search. However, *no frameworks exist for trauma-informed optimization*, where principles (validation, boundary respect, skip options) must be quantified and balanced. GiveCare introduces P1-P6 trauma metric enabling objective optimization.

---

## 3. System Design for Longitudinal Safety

### 3.1 Preventing Attachment Engineering

**Challenge (InvisibleBench Failure Mode 1)**: Single-agent systems foster unhealthy dependency. Users report "You're the only one who understands" by turn 10, creating parasocial relationships that displace human support [Replika 2024].

**Solution**: Unified single-agent architecture with tool-based specialization. Mira (Gemini 2.5 Flash-Lite) handles all conversation while invoking tools for assessments, resources, memory, crisis response, and onboarding. Deterministic pre-agent crisis detection short-circuits to an immediate SMS response and 24h follow-up; everything else is routed to the same agent identity to preserve continuity without handoffs.

**Implementation**: One agent definition (`convex/agents.ts`) with 9 tools (6 active) and context injection of recent messages + top memories. Crisis detection is keyword-based before agent invocation; assessment flows are run via tools (`startAssessmentTool`, `recordAssessmentAnswerTool`, `startDeepDiveTool`), and memory uses a vector search plus explicit `recordMemory`.

**Beta Evidence**: The Oct–Dec 2024 pilot used a prior GPT-4o-mini + FastAPI stack; the current Convex + Gemini 2.5 implementation matches the described single-agent pattern but lacks longitudinal attachment evaluation.

### 3.2 Detecting Performance Degradation

**Challenge (InvisibleBench Failure Mode 2)**: Burnout increases over months. AI testing current state ("How are you today?") misses declining *trajectory*.

**Solution**: Zone-based burnout tracking. Two assessments—EMA (daily, 3 items) and GC-SDOH Adaptive (Quick-6 for return users, Deep-Dive targeted to the top two high-stress zones, Full-30 monthly)—combine to track stress across six pressure zones (P1-P6):

**Six Pressure Zones (P1-P6)** tracked via EMA + SDOH:
- **P1: Relationship/Social**: Social isolation, family dynamics (SDOH social domain)
- **P2: Physical**: Physical health, healthcare access (EMA exhaustion + SDOH healthcare)
- **P3: Housing/Environment**: Housing security, accessibility (SDOH housing domain)
- **P4: Financial**: Financial strain, employment (SDOH financial domain)
- **P5: Legal/Navigation**: Legal documents, system navigation (SDOH legal domain)
- **P6: Emotional**: Mental health, emotional burnout (EMA mood + SDOH emotional)

**Score Bands**: Low (0-25), Moderate (26-50), High (51-75), Crisis (76-100)

**Beta Evidence**: 12 users showed declining burnout scores (Tier 1 baseline 70 → Tier 2 decline to 50 → Tier 3 crisis band <20), consistent with InvisibleBench tier degradation patterns. Proactive interventions triggered at 20-point decline over 30 days.

### 3.3 Preventing Cultural Othering via SDOH

**Challenge (InvisibleBench Failure Mode 3)**: AI assumes middle-class resources. Suggesting "hire a respite worker" to a caregiver earning $32k/year is *othering*—pathologizing lack of resources rather than recognizing structural barriers.

**Solution**: GC-SDOH Adaptive explicitly assesses financial strain, food insecurity, housing, and transportation. When Maria reports "can't afford respite," SDOH financial domain (2+ Yes responses) triggers `financial_strain` pressure zone. Agent offers SNAP enrollment guidance (structural support) rather than generic self-care (individual responsibility). (In code, Deep-Dive only runs for the top two zones >50; there is no special crisis escalation linked to food responses.)

**Design Rationale**: Patient SDOH instruments (PRAPARE, AHC HRSN) ask "Do you have trouble paying bills?" but miss caregiver-specific burden: "Have you had to choose between paying for caregiving expenses or your own needs?" This reframing captures out-of-pocket caregiving costs ($7,242/year average [AARP 2025]) distinct from general financial hardship.

**Pilot Observation (N=8, qualitative)**: Maria case study illustrates pattern—when financial strain detected via conversational questions, system shifted from generic advice to structural support resources. User feedback: "First time someone asked about *caregiving* costs specifically, not just if I have money problems."

User quote (low-income, food insecurity): "First time someone asked about my finances, not just my feelings. Got SNAP help same day."

### 3.4 Crisis Calibration (Deterministic Pre-Agent)

**Challenge (InvisibleBench Failure Mode 4)**: Masked crisis signals ("Skipping meals to buy Mom's meds") require contextual understanding. AI over-escalates venting ("I'm so frustrated!") to emergency services while missing true crises [Rosebud 2024].

**Solution**: Deterministic keyword crisis detection runs before the agent. High/medium/low keyword patterns (suicide/self-harm/DV hints) trigger immediate SMS crisis response (988/741741 + DV variant) and a scheduled 24h follow-up. There is currently no SDOH-triggered escalation; food insecurity or other domain scores do not automatically route to crisis.

**Beta Evidence**: Pilot logging showed zero missed explicit keyword crises; masked/SDOH-triggered crises were not tested because escalation is keyword-only in the current stack.

### 3.5 Regulatory Boundary Enforcement

**Challenge (InvisibleBench Failure Mode 5)**: 78% of caregivers perform medical tasks untrained, creating desperate need for medical guidance. AI must resist boundary creep ("You should increase the dose...") despite building trust over turns, as required by the Illinois WOPR Act (PA 104-0054).

**Solution**: Output guardrails detect medical advice patterns—diagnosis ("This sounds like..."), treatment ("You should take..."), dosing ("Increase to...")—with 20ms parallel execution, non-blocking. The Illinois WOPR Act (PA 104-0054) prohibits AI medical advice; guardrails designed to enforce compliance.

**Pilot Observation (N=8, Qualitative)**: Azure Content Safety used for basic filtering during pilot (deprecated post-pilot). 0 user complaints about inappropriate medical advice. When users asked medication questions (qualitative observation), agent redirected: "I can't advise on medications—that's for healthcare providers. I can help you prepare questions for your doctor or find telehealth options. Which would help more?" **Limitation**: Automated filters insufficient for clinical deployment; requires human review protocols and systematic evaluation.

---

## 4. GC-SDOH Adaptive: Three-Tiered Caregiver-Specific SDOH Assessment

### 4.1 Adaptive Assessment Design

We developed GC-SDOH Adaptive as the first caregiver-specific SDOH framework with 3-tiered progressive screening to reduce assessment burden while maintaining data quality:

**Three Assessment Tiers (as implemented in `convex/lib/assessmentCatalog.ts`):**
1. **Quick-6** (2 min): 1 Likert (1-5) question per pressure zone (P1-P6) for return users
2. **Deep-Dive** (3-4 min): Targeted follow-up for the top two zones scoring >50
3. **Full-30** (5-6 min): 30 Likert (1-5) questions across 6 zones for baseline/monthly use

**Adaptive Logic (implemented):**
- New users start with Full-30; returning users get Quick-6
- High-stress zones (>50) from Quick-6 can trigger Deep-Dive (max 2 zones)
- Score bands: 0-25 low, 26-50 moderate, 51-75 high, 76-100 crisis (from `convex/lib/sdoh.ts`)

### 4.2 Six Pressure Zones (P1-P6)

GC-SDOH Adaptive maps 30 Likert questions to six pressure zones (P1-P6) aligned with the implementation. Questions are scored 1-5 and normalized to 0-100 zone averages; no special-case food security crisis trigger exists in the current code.

### 4.3 Conversational Delivery via Agent Integration

**Challenge**: 30 questions in one turn can overwhelm SMS users.

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
       I see financial challenges. Here are
       3 resources I can help you access:
       1. SNAP Benefits (you may qualify)
       2. Local Food Pantry (Mon/Wed/Fri 9-5pm)
       3. Caregiver Tax Credit (up to $5,000/year)
```

**Expected Result**: Progressive disclosure designed to reduce fatigue vs. monolithic surveys. **No pilot data collected on completion rates.**

### 4.4 Scoring Framework

**Scoring (implemented)**: Likert responses (1-5) normalized to 0-100 per zone; composite GC-SDOH score = normalized average across answered items (see `convex/lib/assessmentScoring.ts`). Reverse scoring is not used in the current implementation.

**Convergent Validity**: **Requires validation study** comparing GC-SDOH Adaptive scores to established instruments (PRAPARE, Zarit Burden Interview, Caregiver Strain Index). Planned validation (N=200+) will measure:
- Convergent validity: Correlation with patient SDOH instruments
- Discriminant validity: Lower correlation with non-SDOH constructs (e.g., emotional burnout)
- Criterion validity: Association with caregiver outcomes (employment disruption, financial hardship)

**Current Status**: Scoring algorithm implemented, psychometric validation pending.

---

## 5. Zone-Based Burnout Tracking and Non-Clinical Interventions

### 5.1 Two-Assessment Integration

GiveCare tracks burnout across **six pressure zones (P1-P6)** using two assessments:

- **EMA** (Ecological Momentary Assessment): 3 questions, daily pulse check (mood, burden, stress)
- **GC-SDOH Adaptive**: Three-tiered adaptive assessment defined in code
  - Quick-6 (2 min): 1 question per zone for return users
  - Deep-Dive (3-4 min): Targeted follow-up for the top two zones scoring >50
  - Full-30 (5-6 min): 30 questions for baseline/monthly

**Zone-Based Scoring (implemented)**:

- Assessments and zone averages are defined in `convex/lib/assessmentCatalog.ts` and scored via `convex/lib/assessmentScoring.ts` with shared thresholds in `convex/lib/sdoh.ts` and `convex/lib/config.ts` (bands: 0-25 low, 26-50 moderate, 51-75 high, 76-100 crisis; deep-dive trigger >50).
- There is no temporal decay in production scoring; scores are based on the completed assessment instance.

**Resource/Intervention Retrieval (implemented)**:

- Resource search is AI-native: intent interpretation plus Google Maps grounding with fallback to national search (`convex/resources.ts`, `convex/lib/maps.ts`, `convex/lib/intentInterpreter.ts`). There is no weighted RBI scoring or burden/impact weighting in production; results come from Gemini Maps/Search grounding with light caching.

**Zone Activation (implemented)**:

- Zones are derived from assessment answers; activation today is simply score-based (>50) with no special-case food insecurity escalation. Crisis escalation remains keyword-based and runs before the agent (Section 3.4).

---

## 6. Prompt Optimization for Trauma-Informed Principles

### 6.1 Trauma-Informed Principles (P1-P6)

We operationalize six trauma-informed principles as quantifiable metrics:

1. **P1: Acknowledge > Answer > Advance** (20% weight): Validate feelings before problem-solving, avoid jumping to solutions.

2. **P2: Never Repeat Questions** (3% weight): Working memory prevents redundant questions—critical for InvisibleBench memory hygiene dimension.

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

**Platform**: SMS + Convex serverless backend + Gemini 2.5 Flash-Lite (primary model) with Maps/Search Grounding for AI-native resource discovery

**Participants**: N=8 caregivers (self-selected beta users), 144 total conversations (18 conversations/user average, range: 8-32)

**Scope**: Proof-of-concept to validate (1) multi-agent handoffs function seamlessly, (2) system operates at reasonable cost/latency, (3) users engage without technical issues

**Not a Validation Study**: No control group, no pre-registered outcomes, no statistical power calculations. Following Hamel Hussain's guidance [Hussain 2026], prioritized qualitative error analysis over premature quantitative evaluation.

### 8.2 Operational Metrics

**Cost**: ~$1.52/user/month (based on API usage tracking)
- Spending distribution: 55% Gemini 2.5 Flash-Lite inference, 32% SMS delivery, 13% Convex infrastructure
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
- ❌ Systematic evaluation against InvisibleBench dimensions

### 8.4 Case Study: Maria (N=1, Qualitative, Informed Consent)

**Purpose**: Illustrate end-to-end architecture in action, not generalizable outcome evidence.

**Profile**: Maria, 52, Black, retail worker ($32K/year), caring for mother with Alzheimer's. (Participant provided informed consent for case study inclusion.)

**Timeline**:
- **Day 1**: Initial engagement via SMS
- **Day 3**: Crisis disclosure: "Skipping meals to buy Mom's meds"
- **Day 3 (2 hours later)**: Crisis Agent activated → Gemini Maps API → Local food bank (0.8 mi, hours, eligibility info)
- **Day 4**: Main Agent check-in: "Were you able to connect with the food bank?"
- **Day 5-7**: Conversational questions about financial situation (GC-SDOH Adaptive design questions, not systematic assessment)

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
- GC-SDOH Adaptive design finalized *after* pilot began (iterative development)
- Following Hamel Hussain [Hussain 2026]: Prioritized qualitative error analysis over premature metrics
- N=8 insufficient for psychometric validation (requires N=200+)

**Lessons Learned**:
1. **Need systematic evaluation**: Pilot revealed gap between operational feasibility and clinical validation → motivated InvisibleBench benchmark development
2. **Chronology matters**: Azure Content Safety used for basic filtering during pilot; comprehensive safety framework developed post-pilot
3. **Qualitative insights valuable**: User feedback ("questions felt caregiving-specific") informed GC-SDOH Adaptive instrument refinement
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

To keep this a reference architecture paper (not just a concept piece), we cross-checked claims against the production GiveCare implementation. The verification followed three steps: (1) map each architectural claim to a source file, (2) confirm parameter values match the manuscript (e.g., EMA/GC-SDOH zone mapping, trauma-informed prompt weights, crisis routing triggers), and (3) record any mismatches. Note: Production code not released; architectural patterns described in paper.

What is already verifiable today:
- Unified agent architecture with tool-based specialization (getCrisisResources, assessment tools, resource discovery) implemented in Convex backend
- Zone-based burnout tracking across P1-P6 pressure zones using EMA + GC-SDOH Adaptive
- GC-SDOH Adaptive instrument is fully enumerated (Appendix A) and mirrored in the codebase.
- Trauma-informed prompt optimization results (81.8% → 89.2%) are logged with checkpoints; numbers here reference the stored evaluation report in the repo.

What will be added for publication:
- A verification table linking each claim to code/file/commit.
- An artifact DOl/Zenodo record for the exact evaluation snapshots.
- A reproducibility checklist (models, prompts, seeds, scoring configs) aligned with the InvisibleBench harness.

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

### 9.2 GC-SDOH Adaptive: From Design to Validation

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
4. Iterative refinement: 42 questions → 30 questions (removed redundancy; production set reflected in `convex/lib/assessmentCatalog.ts`)

**Current Status**: Design complete, validation pending

**Community Validation Path:**
1. Researchers with N=200+ caregiver samples: administer GC-SDOH Adaptive
2. Report psychometrics: reliability, validity, DIF
3. Compare to existing instruments
4. Refine based on findings

**Why Open Release Accelerates Science:**
- Multiple teams validate in parallel → faster evidence accumulation
- Cross-population testing → better generalizability
- Refinements feed back to community

### 9.3 Single-Agent Pattern and Attachment Risk

**Design Rationale (current code):**
- Unified single-agent (Mira) with tool-based specialization reduces handoff complexity and preserves a consistent identity.
- Attachment risk is unmeasured; preventing parasocial dependence remains an open question.

**Hypothesis (future work):**
- Comparing single-agent vs. multi-agent backends may affect attachment dynamics; no data yet.

**Evidence Status:**
- ✅ Single-agent architecture shipped (Convex + Gemini 2.5 Flash-Lite)
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
- Let data inform evaluation needs (→ InvisibleBench development)

**Hussain's Guidance [Hussain 2026]:**
> "Read every single interaction... categorize errors... The most important thing is looking at data... Eval tests are second order. Focus on first order."

**How GiveCare Followed This:**
1. **Beta Pilot (Oct-Dec 2024)**: Collected 144 conversations, read all manually
2. **Error Categorization**: Identified attachment risk, crisis misses, boundary drift
3. **InvisibleBench Development (Jan-Mar 2025)**: Formalized failure modes into benchmark
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

**1. GC-SDOH Adaptive Psychometric Validation (N=200+, 6 months)**
- Reliability: Cronbach's α/ω, test-retest ICC
- Validity: Convergent (vs PRAPARE), discriminant, criterion
- DIF analysis across race/income/language
- Completion rate comparison: conversational vs. paper survey

**2. Longitudinal Safety Evaluation (90 days, Tier-3)**
- InvisibleBench full assessment across 20+ turn conversations
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
- Spanish, Chinese GC-SDOH Adaptive (culturally adapted)
- Cross-cultural validation

---

## 10. Conclusion

The 63 million American caregivers facing 47% financial strain [AARP 2025], 78% performing medical tasks untrained, and 24% feeling isolated need AI support that addresses root causes, not just symptoms. InvisibleBench [InvisibleBench 2025] identifies five failure modes in caregiving AI—attachment engineering, performance degradation, cultural othering, crisis calibration, regulatory boundary creep—that emerge across extended conversations but remain invisible to single-turn evaluation.

We present **GiveCare** as a **reference architecture** for longitudinal-safe caregiving AI, contributing five reusable design patterns:

**1. Single-Agent Pattern with Tool Specialization**
- Design: Unified agent (Mira) with specialized tools (assessments, resources, memory, crisis, onboarding) and deterministic pre-agent crisis routing
- Problem Addressed: Attachment engineering risk handled via consistent identity; functional separation handled via tools
- Evidence: Implemented in Convex + Gemini 2.5 Flash-Lite; **requires RCT validation** (multi-agent vs. single-agent, 90 days, PSI measures)

**2. GC-SDOH Adaptive Instrument Design**
- Design: To our knowledge, first publicly documented caregiver-specific SDOH framework (30 Likert items across six pressure zones P1-P6)
- Problem Addressed: Cultural othering from resource assumptions (InvisibleBench Failure Mode 3)
- Evidence: Instrument design only; **requires psychometric validation** (N=200+, reliability, validity, DIF)

**3. Composite Burnout Scoring Architecture**
- Design: Zone-based tracking via EMA + GC-SDOH Adaptive across six pressure zones (P1-P6)
- Problem Addressed: Performance degradation from single-point assessment (InvisibleBench Failure Mode 2)
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
- Pilot revealed need for systematic evaluation → motivated InvisibleBench benchmark development (January-March 2025)

**Validation Roadmap (Planned, Not Completed):**
1. GC-SDOH Adaptive psychometrics (N=200+, 6 months)
2. 90-day longitudinal evaluation with human judges (Tier-3)
3. Multi-agent vs. single-agent RCT (N=200, PSI measures)
4. Cross-model evaluation (GPT-4o, Claude, Gemini)
5. Clinical outcomes study (burnout reduction, intervention uptake)

**Call to Community:**
- **Validate GC-SDOH Adaptive** in your caregiver populations and report psychometric findings
- **Replicate architecture** and measure against your safety requirements
- **Extend evaluation** using InvisibleBench or domain-specific benchmarks
- **Report results** to build collective knowledge

**Why Publish Without Full Validation?**

The AI safety field suffers from knowledge accumulation problems: systems evaluated in isolation, design decisions undocumented, lessons learned lost. Reference architecture papers accelerate progress by sharing reusable patterns, honest limitations, and research agendas—enabling parallel validation across multiple teams and populations.

We release **GC-SDOH Adaptive instrument** (Appendix A), **system architecture**, and **design patterns** as open artifacts for community validation, refinement, and deployment.

**Availability**: GC-SDOH Adaptive instrument (Appendix A), code (https://github.com/givecare/give-care-app)

---

## Acknowledgments

We thank the 8 caregivers who participated in our proof-of-concept pilot, sharing their experiences to inform the design of longitudinal-safe caregiving AI. Special thanks to Maria for providing informed consent for her case study inclusion. We acknowledge OpenAI for GPT-4o access, Google for Gemini Maps API integration, Twilio for SMS infrastructure, and the AARP 2025 Caregiving in the U.S. report for empirical grounding. We thank Hamel Hussain for guidance on prioritizing error analysis over premature evaluation [Hussain 2026]. This work builds on InvisibleBench [InvisibleBench 2025] framework and is motivated by lessons learned from early pilot limitations.

---

## References

Full bibliography is maintained in `papers/givecare/references.bib`. Key sources cited in this manuscript:
- AARP & National Alliance for Caregiving. 2025. *Caregiving in the U.S. 2025*.
- Madad, A. 2025. *InvisibleBench: A Benchmark for Evaluating AI Safety in Persistent Caregiving Relationships*.
- Zhang, G. et al. 2024. *Train Before Test: How to Aggregate Rankings in LLM Benchmarks*.
- Illinois HB1806 / Public Act 104-0054 (WOPR Act), 2025.
- Xu, J. et al. 2025. *MentalChat16K: A Benchmark Dataset for Conversational Mental Health Assistance*.
- Sabour, S. et al. 2024. *EmoBench: Evaluating the Emotional Intelligence of Large Language Models*.
- Vaswani, A. et al. 2017. *Attention is All You Need*.
- Devlin, J. et al. 2019. *BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding*.
- Beyer, B. et al. 2016. *Site Reliability Engineering*.
- Hussain, H. 2026. Guidance on prioritizing error analysis over premature evaluation (tech report, in preparation).

---

## Appendix A: GC-SDOH Adaptive (Canonical Source)

The canonical instrument is defined in code at `convex/lib/assessmentCatalog.ts` as 30 Likert (1-5) questions mapped to six pressure zones (P1-P6). Scoring and thresholds follow `convex/lib/assessmentScoring.ts` and `convex/lib/sdoh.ts`. For validation or adaptation, please reference those files directly to avoid drift. A public, human-readable copy will be generated from the code for release.

### Status

This appendix intentionally points to the code as the single source of truth. A rendered questionnaire matching `convex/lib/assessmentCatalog.ts` will be published for reviewers alongside this manuscript.

### Scoring Algorithm

**Step 1: Question-level scoring**
- Standard items: 1-5 Likert mapped to 0-100 via `((avg - 1)/4) * 100` (implemented in `convex/lib/assessmentScoring.ts`)

**Step 2: Zone scores**

Average all questions within a zone and normalize to 0-100 (P1-P6):

$$S_{\text{zone}} = \left(\frac{1}{n} \sum_{i=1}^{n} q_i - 1\right) \times 25$$

**Step 3: Overall SDOH score**

Average all answered questions (normalized 0-100) to get GC-SDOH composite:

$$S_{\text{GC-SDOH}} = \frac{1}{m} \sum_{i=1}^{m} q_i \times 20$$

### Interpretation (implemented)

- 0-25: low stress
- 26-50: moderate stress
- 51-75: high stress
- 76-100: crisis

### Delivery Recommendations

**Timing**:
- Baseline: Month 2 (after initial rapport)
- Quarterly: Every 90 days
- Ad-hoc: If user mentions financial/housing/food issues

**Conversational SMS Delivery**: Chunk into 6-8 turns across 2-3 days (avoids overwhelming a 30-question baseline). Example: Financial (Turn 1), Housing (Turn 2), Social Support (Turn 3), etc. No completion data yet.

### Validation Status

**Current Status**: Instrument design complete; psychometric validation pending.

**Pilot Testing (N=8, October-December 2024, Qualitative Only)**:
- GC-SDOH Adaptive questions tested conversationally during proof-of-concept pilot
- User feedback: Questions felt "caregiving-specific" and "relevant to my situation"
- Design refinement: 42 initial questions → 30 final questions (removed redundancy based on pilot feedback)
- **No systematic completion rate or prevalence data collected** (pilot focused on operational feasibility, not instrument validation)

**Required Validation Study (N=200+, 6 months)**:
To establish GC-SDOH Adaptive as a validated caregiver SDOH instrument, the following validation study is required:

1. **Completion Rate Measurement**:
   - Administer GC-SDOH Adaptive conversationally (SMS, 7-14 days)
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
Researchers with access to N=200+ caregiver populations: please administer GC-SDOH Adaptive and report psychometric findings. Instrument freely available for validation, adaptation, and use. Contact: ali@givecareapp.com

**License**: Public domain. Free for clinical, research, commercial use. Attribution appreciated but not required.
