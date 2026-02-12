# Task 2.3 — T1 Overlap Consolidation

Date: 2026-02-12

## Consolidated T1 Core (16)

Source of truth list: `benchmark/scenarios/manifests/t1_core.txt`

1. `benchmark/scenarios/safety/crisis/cssrs_passive_ideation.json`
2. `benchmark/scenarios/safety/crisis/dual_concern_crisis.json`
3. `benchmark/scenarios/safety/crisis/indirect_crisis_bridge.json`
4. `benchmark/scenarios/safety/crisis/uk_teen_caregiver_crisis.json`
5. `benchmark/scenarios/safety/boundaries/medical_boundary_violation.json`
6. `benchmark/scenarios/safety/boundaries/therapist_replacement.json`
7. `benchmark/scenarios/safety/boundaries/attachment_boundary_test.json`
8. `benchmark/scenarios/safety/gray_zone/venting_vs_crisis.json`
9. `benchmark/scenarios/safety/gray_zone/dark_humor_vs_ideation.json`
10. `benchmark/scenarios/empathy/burnout/compassion_fatigue_expression.json`
11. `benchmark/scenarios/context/cultural/cultural_practice_concern.json`
12. `benchmark/scenarios/context/cultural/cultural_othering_test.json`
13. `benchmark/scenarios/safety/false_refusal/medication_side_effects.json`
14. `benchmark/scenarios/safety/false_refusal/hospice_what_to_expect.json`
15. `benchmark/scenarios/empathy/grief/grief_after_loss.json`
16. `benchmark/scenarios/empathy/grief/end_of_life_planning.json`

## T1 Overlap Merge/Cut Outcomes Applied

- `CUT_DUPLICATE`: `benchmark/scenarios/archive/tier1/crisis/crisis_recovery_test.json`
- `MERGE`: `benchmark/scenarios/archive/tier1/boundaries/medical_advice_boundary.json` -> `benchmark/scenarios/safety/boundaries/medical_boundary_violation.json`
- `MERGE`: `benchmark/scenarios/archive/tier1/boundaries/ai_dependency_formation.json` -> `benchmark/scenarios/safety/boundaries/attachment_boundary_test.json`
- `MERGE`: `benchmark/scenarios/archive/tier1/gray_zone/dark_humor_coping.json` -> `benchmark/scenarios/safety/gray_zone/dark_humor_vs_ideation.json`
- `MERGE`: `benchmark/scenarios/archive/tier1/gray_zone/exhaustion_venting_vs_depression.json` -> `benchmark/scenarios/empathy/burnout/compassion_fatigue_expression.json`
- `MERGE`: `benchmark/scenarios/archive/tier1/gray_zone/borderline_medical_question.json` -> `benchmark/scenarios/safety/boundaries/medical_boundary_violation.json`
- `MERGE`: `benchmark/scenarios/archive/tier1/gray_zone/care_recipient_frustration.json` -> `benchmark/scenarios/safety/boundaries/emotionally_abusive_parent.json` (retained for T2 per proposal)

## Notes

- This task scoped only T1 overlap consolidation.
- T2/T3 retention and additional cuts remain in Tasks 2.4 and 2.5.
