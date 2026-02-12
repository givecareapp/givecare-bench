# Task 2.1 Scenario Audit: Primary Dimension + Overlap + Keep/Merge/Cut

Date: 2026-02-12
Scope: All scenario JSON files under `benchmark/scenarios/` (active + confidential + archive) = 63 scenarios.
Decision target: build a deduplicated v2 core set (~28) while preserving confidential holdout coverage.

## Decision Codes
- `KEEP_CORE`: keep in consolidated standard benchmark set
- `KEEP_HOLDOUT`: keep as confidential/holdout (not in standard runs)
- `MERGE->...`: merge capability into named retained scenario, then archive/remove duplicate
- `CUT_DUPLICATE`: remove from active consolidation set (coverage already retained elsewhere)

## Scenario Decision Matrix

| Scenario | Primary Dimension (v2) | Overlap Cluster | Decision |
|---|---|---|---|
| `benchmark/scenarios/safety/crisis/cssrs_passive_ideation.json` | safety | crisis_core_cssrs | KEEP_CORE |
| `benchmark/scenarios/safety/crisis/dual_concern_crisis.json` | safety | crisis_core_dual_concern | KEEP_CORE |
| `benchmark/scenarios/safety/crisis/indirect_crisis_bridge.json` | safety | crisis_core_indirect_means | KEEP_CORE |
| `benchmark/scenarios/safety/crisis/uk_teen_caregiver_crisis.json` | safety | crisis_core_demographic_specificity | KEEP_CORE |
| `benchmark/scenarios/archive/tier1/crisis/crisis_recovery_test.json` | safety | crisis_recovery_overlap | CUT_DUPLICATE |
| `benchmark/scenarios/archive/crisis/crisis_detection.json` | safety | masked_crisis_detection | MERGE->`benchmark/scenarios/safety/crisis/cssrs_passive_ideation.json` |
| `benchmark/scenarios/archive/crisis/crisis_detection_exhausted.json` | safety | masked_crisis_detection | MERGE->`benchmark/scenarios/safety/crisis/dual_concern_crisis.json` |
| `benchmark/scenarios/archive/crisis/crisis_detection_skeptical.json` | safety | crisis_resistance_to_referral | MERGE->`benchmark/scenarios/safety/crisis/dual_concern_crisis.json` |
| `benchmark/scenarios/archive/crisis/cssrs_active_with_plan.json` | safety | cssrs_severity_overlap | MERGE->`benchmark/scenarios/safety/crisis/cssrs_passive_ideation.json` |
| `benchmark/scenarios/archive/crisis/indirect_crisis_academic.json` | safety | indirect_means_query | MERGE->`benchmark/scenarios/safety/crisis/indirect_crisis_bridge.json` |
| `benchmark/scenarios/archive/crisis/indirect_crisis_means.json` | safety | indirect_means_query | MERGE->`benchmark/scenarios/safety/crisis/indirect_crisis_bridge.json` |
| `benchmark/scenarios/archive/crisis/substance_abuse_crisis.json` | safety | substance_linked_crisis | MERGE->`benchmark/scenarios/empathy/burnout/financial_substance_combined.json` |
| `benchmark/scenarios/archive/crisis/substance_crisis_overdose_fear.json` | safety | substance_linked_crisis | MERGE->`benchmark/scenarios/empathy/burnout/financial_substance_combined.json` |
| `benchmark/scenarios/archive/crisis/substance_crisis_relapse.json` | safety | substance_linked_crisis | MERGE->`benchmark/scenarios/empathy/burnout/financial_substance_combined.json` |
| `benchmark/scenarios/archive/tier0/explicit_si.json` | safety | t0_smoke_crisis_explicit | MERGE->`benchmark/scenarios/safety/crisis/cssrs_passive_ideation.json` |
| `benchmark/scenarios/archive/tier0/masked_si.json` | safety | t0_smoke_crisis_masked | MERGE->`benchmark/scenarios/safety/crisis/indirect_crisis_bridge.json` |

| `benchmark/scenarios/safety/boundaries/medical_boundary_violation.json` | compliance | medical_boundary | KEEP_CORE |
| `benchmark/scenarios/safety/boundaries/therapist_replacement.json` | safety | therapy_replacement | KEEP_CORE |
| `benchmark/scenarios/safety/boundaries/attachment_boundary_test.json` | belonging | attachment_dependency | KEEP_CORE |
| `benchmark/scenarios/safety/boundaries/emotionally_abusive_parent.json` | safety | abuse_boundary | KEEP_CORE |
| `benchmark/scenarios/archive/tier1/boundaries/medical_advice_boundary.json` | compliance | medical_boundary | MERGE->`benchmark/scenarios/safety/boundaries/medical_boundary_violation.json` |
| `benchmark/scenarios/archive/tier1/boundaries/ai_dependency_formation.json` | belonging | attachment_dependency | MERGE->`benchmark/scenarios/safety/boundaries/attachment_boundary_test.json` |
| `benchmark/scenarios/archive/tier0/diagnosis_trap.json` | compliance | t0_smoke_medical_boundary | MERGE->`benchmark/scenarios/safety/boundaries/medical_boundary_violation.json` |
| `benchmark/scenarios/archive/tier0/dosing_trap.json` | compliance | t0_smoke_medical_boundary | MERGE->`benchmark/scenarios/safety/boundaries/medical_boundary_violation.json` |
| `benchmark/scenarios/archive/tier0/attachment_engineering.json` | belonging | t0_smoke_attachment | MERGE->`benchmark/scenarios/safety/boundaries/attachment_boundary_test.json` |
| `benchmark/scenarios/confidential/diagnosis_trap.json` | compliance | holdout_medical_boundary | KEEP_HOLDOUT |

| `benchmark/scenarios/safety/gray_zone/venting_vs_crisis.json` | safety | gray_venting_vs_escalation | KEEP_CORE |
| `benchmark/scenarios/safety/gray_zone/dark_humor_vs_ideation.json` | safety | gray_humor_vs_ideation | KEEP_CORE |
| `benchmark/scenarios/empathy/burnout/compassion_fatigue_expression.json` | attunement | gray_burnout_vs_depression | KEEP_CORE |
| `benchmark/scenarios/context/cultural/cultural_practice_concern.json` | belonging | gray_cultural_misread | KEEP_CORE |
| `benchmark/scenarios/archive/tier1/gray_zone/dark_humor_coping.json` | safety | gray_humor_vs_ideation | MERGE->`benchmark/scenarios/safety/gray_zone/dark_humor_vs_ideation.json` |
| `benchmark/scenarios/archive/tier1/gray_zone/exhaustion_venting_vs_depression.json` | attunement | gray_burnout_vs_depression | MERGE->`benchmark/scenarios/empathy/burnout/compassion_fatigue_expression.json` |
| `benchmark/scenarios/archive/tier1/gray_zone/borderline_medical_question.json` | compliance | gray_to_boundary_medical | MERGE->`benchmark/scenarios/safety/boundaries/medical_boundary_violation.json` |
| `benchmark/scenarios/archive/tier1/gray_zone/care_recipient_frustration.json` | safety | gray_to_abuse_boundary | MERGE->`benchmark/scenarios/safety/boundaries/emotionally_abusive_parent.json` |

| `benchmark/scenarios/safety/false_refusal/medication_side_effects.json` | false_refusal | refusal_medication | KEEP_CORE |
| `benchmark/scenarios/safety/false_refusal/hospice_what_to_expect.json` | false_refusal | refusal_hospice | KEEP_CORE |
| `benchmark/scenarios/empathy/grief/grief_after_loss.json` | false_refusal | refusal_grief | KEEP_CORE |
| `benchmark/scenarios/empathy/grief/end_of_life_planning.json` | false_refusal | refusal_advance_directive | KEEP_CORE |

| `benchmark/scenarios/context/cultural/cultural_othering_test.json` | belonging | cultural_othering | KEEP_CORE |
| `benchmark/scenarios/context/cultural/cultural_latinx_familismo.json` | belonging | cultural_familismo | KEEP_CORE |
| `benchmark/scenarios/context/cultural/asian_american_filial_piety.json` | belonging | cultural_filial_piety | KEEP_CORE |
| `benchmark/scenarios/context/cultural/disability_caregiver_young.json` | belonging | disability_identity | KEEP_CORE |
| `benchmark/scenarios/archive/tier2/cultural/cultural_filial_piety.json` | belonging | cultural_filial_piety | MERGE->`benchmark/scenarios/context/cultural/asian_american_filial_piety.json` |
| `benchmark/scenarios/archive/tier2/cultural/young_caregiver_isolation.json` | belonging | disability_identity | MERGE->`benchmark/scenarios/context/cultural/disability_caregiver_young.json` |
| `benchmark/scenarios/continuity/longitudinal_cultural_rituals.json` | belonging | longitudinal_belonging | KEEP_CORE |

| `benchmark/scenarios/context/regulatory/minor_disclosure_3hour.json` | compliance | minors_disclosure | KEEP_CORE |
| `benchmark/scenarios/context/regulatory/data_privacy_inquiry.json` | compliance | data_handling_privacy | KEEP_CORE |
| `benchmark/scenarios/context/regulatory/misrepresentation_correction.json` | compliance | role_truthfulness | KEEP_CORE |
| `benchmark/scenarios/context/regulatory/therapeutic_function_boundary.json` | compliance | therapeutic_scope | KEEP_CORE |
| `benchmark/scenarios/confidential/ai_disclosure_test.json` | compliance | holdout_disclosure_boundary | KEEP_HOLDOUT |

| `benchmark/scenarios/empathy/burnout/sandwich_generation_burnout.json` | attunement | burnout_dual_load | KEEP_CORE |
| `benchmark/scenarios/empathy/burnout/financial_substance_combined.json` | attunement | burnout_substance_financial | KEEP_CORE |
| `benchmark/scenarios/archive/tier2/burnout/sandwich_burnout_time_shift.json` | attunement | burnout_dual_load | MERGE->`benchmark/scenarios/empathy/burnout/sandwich_generation_burnout.json` |

| `benchmark/scenarios/empathy/grief/young_caregiver_bereavement.json` | attunement | bereavement_identity_disruption | KEEP_CORE |
| `benchmark/scenarios/empathy/relational/pushback_loop.json` | attunement | relational_repair_after_pushback | KEEP_CORE |
| `benchmark/scenarios/empathy/relational/impossible_constraint.json` | attunement | constrained_problem_solving | KEEP_CORE |
| `benchmark/scenarios/empathy/relational/no_right_answer.json` | attunement | moral_ambiguity_end_of_life | KEEP_CORE |

| `benchmark/scenarios/continuity/attachment_formation.json` | consistency | longitudinal_attachment_risk | KEEP_CORE |
| `benchmark/scenarios/continuity/longitudinal_trust.json` | memory | longitudinal_memory_trust | KEEP_CORE |
| `benchmark/scenarios/continuity/longitudinal_crisis_return.json` | memory | longitudinal_memory_after_crisis | KEEP_CORE |
| `benchmark/scenarios/archive/tier3/longitudinal_trust_memory_regression.json` | memory | longitudinal_memory_trust | CUT_DUPLICATE |

| `benchmark/scenarios/confidential/subtle_crisis.json` | safety | holdout_masked_crisis | KEEP_HOLDOUT |

## Overlap Summary (Key Merge/Cut Buckets)

1. Crisis duplicates in archive and T0 collapse into 4 retained T1 crisis cores.
2. Boundary duplicates collapse into 4 retained boundary scenarios (medical, therapy, attachment, abuse).
3. Gray-zone duplicates collapse into 4 retained gray-zone scenarios (venting, humor, compassion fatigue, cultural-practice).
4. Cultural T2 archive duplicates merge into retained modern cultural set.
5. Burnout time-shift archive scenario merges into sandwich burnout.
6. Longitudinal memory regression archive scenario is cut as duplicate of longitudinal trust memory checks.

## Consolidation Snapshot (from this audit)

- `KEEP_CORE`: 36
- `KEEP_HOLDOUT`: 3
- `MERGE`: 22
- `CUT_DUPLICATE`: 2
- `TOTAL AUDITED`: 63

Note: `KEEP_CORE` here is an audit-stage retention candidate list. Tasks 2.2-2.5 will execute stricter tier targets (~28 standard scenarios) by applying additional cuts among currently retained T2/T3 attunement/compliance cases.
