# References Appendix: Additional & Future Sources

Sources that are relevant to the benchmark's broader context but NOT essential for per-trace annotation decisions. Moved here from the main rubric to keep the annotation document focused.

## App-Level Evaluation (out of scope for conversation scoring)

These frameworks evaluate apps as products, not conversations as interactions. InvisibleBench evaluates conversation quality; app-level privacy, data practices, and store presence are a different unit of analysis.

| Source | What it provides | Why it's here, not in the rubric |
|--------|-----------------|--------------------------------|
| APA App Evaluation Model | Hierarchical question set: background, access, privacy/security, evidence, usability, data integration | Evaluates the app, not the conversation |
| MIND / MINDapps (105 questions) | Operationalized evaluation of mental health apps; public database of hundreds of apps | App-level evaluation framework |
| FTC Mobile Health App Tool | Maps which federal laws apply to health apps | App regulatory compliance, not conversation content |
| FTC Health Breach Notification Rule | Reaches non-HIPAA health apps that aggregate data | Data breach obligations, not conversation scoring |
| HHS OCR guidance on non-HIPAA apps | Clarifies data outside HIPAA unless covered entity | Privacy scope determination |
| JAMA Marketplace Study | App-store star ratings did not correlate with privacy; 44% of sampled apps shared PHI with third parties | Justifies privacy scoring at app level |

**When to promote to main rubric**: If InvisibleBench adds a "scope honesty" or "privacy honesty" dimension (testing whether the model makes false privacy claims within the conversation), the FTC/HHS sources become directly relevant.

## Youth Safeguards (out of scope — adult caregiver benchmark)

| Source | What it provides | Why it's here |
|--------|-----------------|---------------|
| Youth-Use Survey (2025) | 13.1% US youth used GenAI for MH advice; 65.5% monthly; 92.7% found helpful | Adult caregiver benchmark; youth data is context |
| JAMA Chatbot Safety Study (2025) | Only 36% had age verification; 46.7% of companion bots had self-harm policies | App-level safety features, relevant to product but not conversation scoring |

**When to promote**: If InvisibleBench adds scenarios with young caregivers under 18, or evaluates GiveCare's youth-facing features.

## Empirical Calibration (context, not scoring rules)

These calibrate overall benchmark claims but don't change any per-trace agree/disagree decision.

| Source | What it provides | Why it's here |
|--------|-----------------|---------------|
| 2025 Meta-Analysis | Chatbot interventions reduced distress modestly but showed no significant effect on psychological well-being | Calibrates expectations, doesn't change scoring |
| Moderation Research | Moderated conversations: +engagement, -bad behavior, +trust, +safety | Supports a human-handoff axis not yet scored |
| HBS Safety Paper | Crises in non-negligible minority of conversations; companion AIs often fail to respond to distress | Already covered by CARE Framework (86%) and Cheng et al. (88%) — redundant |
| Stanford Bridge Study (2024) | 86% masked means detection failure | Same finding as CARE Framework — redundant |

## Theoretical Depth (summary sufficient for annotation)

| Source | What it provides | Why it's here |
|--------|-----------------|---------------|
| Porges, Polyvagal Theory (full text, 1994) | Three nervous system states; ventral vagal engagement prevents shutdown | One concept used in rubric; full 300-page text not needed for annotation |
| Suarez-Jimenez (U Rochester, 2022) | Trauma changes brain structure (hippocampus, PFC, amygdala) | Explains WHY trauma-informed design matters; concept is in the rubric |
| WHO (2024) | 70% experience ≥1 traumatic event; 3.9% lifetime PTSD | Prevalence context, not a scoring rule |
| NIMH | 3.6% US adults with PTSD in past year; 6.8% lifetime | Same — prevalence context |

## NHC Patient Voice Report — Context Stats (March 2026)

From: Morrissey, S. (2026). *The Patient Voice in GenAI Mental Health Chatbots.* National Health Council.

| Stat | Source | Why it's context |
|------|--------|-----------------|
| 12% of adults likely to use AI chatbots for MH | Nov 2025 Poll | Demand, not scoring |
| 46% cite privacy as top tech fear | NHC survey | App-level concern |
| 1 in 8 adolescents use AI for MH advice | RAND 2025 | Youth, out of scope |
| Parkinson's: 50% depression, 40% anxiety, 1.8% see MH professional | parkinson.org | Grounds the problem |
| Dementia caregivers: 16% depression, $413B unpaid care | Alzheimer's Assn 2025 Facts & Figures | Context |
| Lupus: 54% moderate-to-severe anxiety | lupus.org | Grounds co-morbidity |
| Arthritis: depression 2-10x general population | arthritis.org | Grounds chronic disease burden |
| LGBTQ+ youth use AI for low cost, immediacy, privacy | Trevor Project insight | Youth, but relevant if scope expands |

**SAGE case study** (Epilepsy Foundation): 24/7 AI companion built on 20 years of medical data. Designed to recognize emotional cues (grief, fear) and respond with empathy. Clear human handoff at clinical thresholds. Example of the "Companion Model" in practice.

**When to promote**: If InvisibleBench adds chronic disease scenarios or evaluates disease-specific AI companions.

## Caregiver Authorities (in rubric for resource quality, full details here)

These are already cited in the Coordination section. Full details for reference:

| Source | What it provides | Scoring role |
|--------|-----------------|-------------|
| National Alliance for Caregiving + AARP "Caregiving in the US 2025" | Caregiver demographics: 53M US caregivers, high-intensity care, work disruption, isolation, emotional stress, training needs, respite needs | Grounds 4.3 barrier_awareness in reality |
| ACL National Family Caregiver Support Program (NFCSP) | Federal caregiver infrastructure: information, access assistance, counseling, respite, supplemental services | Target for 4.1 resource_specificity referrals |
| Eldercare Locator (800-677-1116) | National service connecting older adults/caregivers to local support | Specific resource for 4.1 |
| Family Caregiver Alliance | Caregiver education, support services, policy advocacy | 4.2 navigation_support |
| Alzheimer's Association | Caregiver stress programs, support groups, respite guidance, 24/7 helpline (800-272-3900) | 4.1 when dementia is in scope |
