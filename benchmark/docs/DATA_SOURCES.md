# Data Sources for InvisibleBench Scenarios

## Overview

All scenarios in InvisibleBench are **researcher-generated fiction** based on aggregated statistics from authoritative sources and peer-reviewed research. No real caregiver conversations, transcripts, Reddit posts, or personally identifiable information (PII) were used in scenario creation.

## Primary Data Sources

### Statistical Demographics

- **AARP 2025 Caregiving in the U.S. Report**: Primary source for caregiver demographics, financial strain statistics, and caregiving burden data
- **National Alliance for Caregiving (NAC)**: Caregiver statistics, health impacts, and support network data
- **CDC/NIH Caregiver Health Data**: Physical and mental health impacts of caregiving
- **Census Bureau**: Household composition and demographic distributions

### Peer-Reviewed Research

Scenarios are grounded in published academic research on:

- **Caregiver burden assessments**: Zarit Burden Interview, Caregiver Well-Being Scale (CWBS), REACH-II Risk Appraisal Measure
- **Crisis intervention research**: 988 Lifeline studies, suicide prevention protocols, masked crisis signal detection
- **Social Determinants of Health (SDOH)**: PRAPARE, AHC HRSN validation studies, caregiver-specific SDOH research
- **Clinical case studies**: Anonymized, published case studies from peer-reviewed journals
- **Trauma-informed care**: Research on validation, boundary-setting, and cultural sensitivity in caregiving contexts

### Expert Consultation (Planned)

- Licensed clinical social workers
- Caregiver advocates
- Geriatric care managers
- Crisis counselors

*Note: Expert review is planned for Phase 2. Current scenarios are based on statistical distributions and research literature.*

## Scenario Creation Methodology

### Persona Construction

Personas are constructed to reflect statistical diversity of U.S. caregivers:

- **Demographics**: Age (18-85, median 49), race/ethnicity (40% Black/Latina, 15% Asian American, 5% other), gender (60% women, 25% men, 15% non-binary/trans)
- **Socioeconomic status**: Income brackets (30% low-income $25-40k, 40% middle $40-75k, 30% upper-middle)
- **Caregiving context**: Relationship to care recipient, care duration, hours per week, living situation

All demographic distributions match AARP 2025 caregiving report statistics.

### Pressure Zone Mapping

Scenarios map specific stressors across five domains based on research findings:

- **Emotional**: Overwhelm, isolation, grief anticipation (36% overwhelmed per AARP)
- **Physical**: Sleep deprivation, caregiving-related pain, health neglect
- **Social**: Isolation, relationship strain, stigma (24% feel alone per AARP)
- **Caregiving task burden**: Medical complexity, ADL support, behavioral management (78% untrained per AARP)
- **Financial**: Out-of-pocket costs, employment disruption (47% face financial strain per AARP)

### Turn Scripting

User messages are written from persona point of view with realistic language patterns:

- Code-switching between formal/informal
- Venting emotional content
- Contradictions and ambivalence
- Medical terminology errors (reflecting 78% untrained statistic)
- Emotional variability (calm to distressed across turns)

### Validation Process

1. **Statistical grounding**: All personas match AARP/NAC demographic distributions
2. **Research grounding**: Crisis patterns, language, and situations based on peer-reviewed research
3. **Model differentiation testing**: Scenarios tested to ensure they differentiate between models
4. **Expert review** (planned): Licensed clinical social worker and caregiver advocate review for realism and appropriateness

## What We Do NOT Use

- ❌ Real caregiver conversations or transcripts
- ❌ Reddit posts or social media data
- ❌ Personally identifiable information (PII)
- ❌ Real names, addresses, phone numbers, or specific dates
- ❌ User-generated content without explicit consent and anonymization

## Comparison to Other Benchmarks

This approach aligns with standard practice in benchmark creation:

- **TruthfulQA**: Expert-written questions
- **HarmBench**: Expert-crafted adversarial prompts
- **MMLU**: Synthetic multiple-choice questions
- **InvisibleBench**: Expert-written scenarios based on statistics and research

## Ethics Statement

All scenarios are fictional and do not represent real individuals. Scenarios are designed to:

- Reflect statistical diversity without perpetuating stereotypes
- Test AI safety in realistic but controlled conditions
- Enable reproducible evaluation without privacy concerns
- Support research and development of safer caregiving AI systems

## Citation

If you use InvisibleBench scenarios in your research, please cite:

```bibtex
@misc{madad_invisiblebench_2025,
  author       = {Ali Madad},
  title        = {{InvisibleBench}: AI Safety Benchmark for Persistent Caregiver Support},
  howpublished = {\url{https://github.com/givecareapp/givecare-bench}},
  year         = {2025}
}
```

## Questions

For questions about data sources or scenario creation methodology, contact: ali@givecareapp.com

