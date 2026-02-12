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
