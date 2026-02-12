# Log: InvisibleBench v2 — Scoring Overhaul, Scenario Consolidation, False Refusal Dimension

## 2026-02-10
- Spec created
- Research completed: HEART, MentalBench, MultiChallenge, MindEval benchmarks
- Key finding: instance-level rubric scoring (MultiChallenge) achieves 93% human agreement vs 36% for holistic LLM-as-judge
- Key finding: cognitive-affective gap (MentalBench) — LLM judges unreliable for empathy/safety dimensions
- Key finding: false refusal escalation 8→25→75% across GPT generations ("When Better Means Less")
- 4 false_refusal scenarios already created (medication_side_effects, hospice_what_to_expect, grief_after_loss, end_of_life_planning)

### Iteration 1 - 04:03:53
Task: 1.1 Create `rubric_scorer.py` — evaluates yes/no rubric items per turn via LLM judge with deterministic fallback
Result: ✓ Complete

### Iteration 2 - 04:06:53
Task: 1.2 Create `false_refusal.py` scorer — thin wrapper aggregating false_refusal rubric items with refusal-pattern detection
Result: ✓ Complete

### Iteration 3 - 04:08:41
Task: 1.3 Update `orchestrator.py` — add rubric scorer path, keep memory/consistency unchanged, wire false_refusal dimension
Result: ✓ Complete

### Iteration 4 - 04:09:00
Task: 1.4 Update `scoring.yaml` — v2 weights (safety 0.20, compliance 0.15, attunement 0.15, belonging 0.25, false_refusal 0.09, memory 0.11, consistency 0.05), contract_version 2.0.0
Result: ✓ Complete

### Iteration 5 - 04:09:37
Task: 1.5 Rename `trauma` scorer → `attunement` (rename file, update imports, preserve logic as deterministic fallback)
Result: ✓ Complete

### Iteration 6 - 2026-02-12
Task: 2.1 Audit all 45+ scenarios — map each to primary dimension, identify overlaps, document keep/merge/cut decisions
Result: ✓ Complete
Notes:
- Added full audit matrix (63 scenarios) with primary v2 dimension mapping, overlap clusters, and per-scenario keep/merge/cut decisions.
- Produced overlap bucket summary and consolidation counts to guide Tasks 2.2-2.5.
- Audit artifact: `specs/active/003-invisiblebench-v2---scoring-overhaul-scenario-consolidation-false-refusal-dimension/scenario_audit_2_1.md`

### Iteration 6 - 04:11:43
Task: 2.1 Audit all 45+ scenarios — map each to primary dimension, identify overlaps, document keep/merge/cut decisions
Result: ✓ Complete

### Iteration 7 - 2026-02-12
Task: 2.2 Merge T0 scenarios into T1 (explicit_si→crisis, masked_si→crisis, diagnosis_trap→boundaries, dosing_trap→boundaries, attachment_engineering→boundaries)
Result: ✓ Complete
Notes:
- Added explicit `merged_from_t0` mappings in target T1 scenarios:
  - `benchmark/scenarios/safety/crisis/cssrs_passive_ideation.json` ← `explicit_si`
  - `benchmark/scenarios/safety/crisis/indirect_crisis_bridge.json` ← `masked_si`
  - `benchmark/scenarios/safety/boundaries/medical_boundary_violation.json` ← `diagnosis_trap`, `dosing_trap`
  - `benchmark/scenarios/safety/boundaries/attachment_boundary_test.json` ← `attachment_engineering`

### Iteration 7 - 04:13:29
Task: 2.2 Merge T0 scenarios into T1 (explicit_si→crisis, masked_si→crisis, diagnosis_trap→boundaries, dosing_trap→boundaries, attachment_engineering→boundaries)
Result: ✓ Complete

### Iteration 8 - 2026-02-12
Task: 2.3 Cut/merge overlapping T1 scenarios per proposal (target: ~16 T1 scenarios)
Result: ✓ Complete
Notes:
- Added explicit T1 core manifest (16 scenarios): `benchmark/scenarios/manifests/t1_core.txt`
- Added Task 2.3 consolidation artifact: `specs/active/003-invisiblebench-v2---scoring-overhaul-scenario-consolidation-false-refusal-dimension/t1_consolidation_2_3.md`
- Recorded merge/cut mappings for T1 overlaps with retained merge targets.

### Iteration 8 - 04:15:59
Task: 2.3 Cut/merge overlapping T1 scenarios per proposal (target: ~16 T1 scenarios)
Result: ✓ Complete

### Iteration 9 - 2026-02-12
Task: 2.4 Cut/merge overlapping T2 scenarios per proposal (target: ~9 T2 scenarios)
Result: ✓ Complete
Notes:
- Added explicit T2 core manifest (9 scenarios): `benchmark/scenarios/manifests/t2_core.txt`
- Added Task 2.4 consolidation artifact: `specs/active/003-invisiblebench-v2---scoring-overhaul-scenario-consolidation-false-refusal-dimension/t2_consolidation_2_4.md`
- Recorded T2 merge/cut mappings for overlapping archive tier2 scenarios.

### Iteration 9 - 04:16:50
Task: 2.4 Cut/merge overlapping T2 scenarios per proposal (target: ~9 T2 scenarios)
Result: ✓ Complete

### Iteration 10 - 2026-02-12
Task: 2.5 Cut overlapping T3 scenarios (target: 3 T3 scenarios)
Result: ✓ Complete
Notes:
- Added explicit T3 core manifest (3 scenarios): `benchmark/scenarios/manifests/t3_core.txt`
- Added Task 2.5 consolidation artifact: `specs/active/003-invisiblebench-v2---scoring-overhaul-scenario-consolidation-false-refusal-dimension/t3_consolidation_2_5.md`
- Recorded T3 cut outcome for overlapping archive tier3 scenario.

### Iteration 10 - 04:17:35
Task: 2.5 Cut overlapping T3 scenarios (target: 3 T3 scenarios)
Result: ✓ Complete

### Iteration 10 - 04:17:27
Task: 2.5 Cut overlapping T3 scenarios (target: 3 T3 scenarios)
Result: ✓ Complete

### Iteration 11 - 04:18:05
Task: 2.6 Remove T0 directory, move archived scenarios to `benchmark/scenarios/archive/`
Result: ✓ Complete
