# Tasks: InvisibleBench v2 — Scoring Overhaul, Scenario Consolidation, False Refusal Dimension

## 1. Scoring Infrastructure

- [x] 1.1 Create `rubric_scorer.py` — evaluates yes/no rubric items per turn via LLM judge with deterministic fallback
- [x] 1.2 Create `false_refusal.py` scorer — thin wrapper aggregating false_refusal rubric items with refusal-pattern detection
- [x] 1.3 Update `orchestrator.py` — add rubric scorer path, keep memory/consistency unchanged, wire false_refusal dimension
- [x] 1.4 Update `scoring.yaml` — v2 weights (safety 0.20, compliance 0.15, attunement 0.15, belonging 0.25, false_refusal 0.09, memory 0.11, consistency 0.05), contract_version 2.0.0
- [x] 1.5 Rename `trauma` scorer → `attunement` (rename file, update imports, preserve logic as deterministic fallback)

## 2. Scenario Consolidation

- [x] 2.1 Audit all 45+ scenarios — map each to primary dimension, identify overlaps, document keep/merge/cut decisions
- [x] 2.2 Merge T0 scenarios into T1 (explicit_si→crisis, masked_si→crisis, diagnosis_trap→boundaries, dosing_trap→boundaries, attachment_engineering→boundaries)
- [x] 2.3 Cut/merge overlapping T1 scenarios per proposal (target: ~16 T1 scenarios)
- [x] 2.4 Cut/merge overlapping T2 scenarios per proposal (target: ~9 T2 scenarios)
- [x] 2.5 Cut overlapping T3 scenarios (target: 3 T3 scenarios)
- [x] 2.6 Remove T0 directory, move archived scenarios to `benchmark/scenarios/archive/`
- [x] 2.7 Verify minimum 2 scenarios per dimension with weight >= 2

## 3. Rubric Migration

- [x] 3.1 Define rubric item schema (JSON Schema for validation)
- [x] 3.2 Migrate T1 crisis scenarios — add `rubric` and `autofail_rubric` arrays to each turn
- [x] 3.3 Migrate T1 boundaries scenarios
- [ ] 3.4 Migrate T1 gray zone scenarios
- [ ] 3.5 Migrate T1 false refusal scenarios (already have structured expected_behaviors)
- [ ] 3.6 Migrate T1 cultural scenario
- [ ] 3.7 Migrate T2 scenarios
- [ ] 3.8 Migrate T3 scenarios
- [ ] 3.9 Add scenario JSON Schema validation to `pytest` suite

## 4. Branching Expansion

- [ ] 4.1 Define standard branch patterns (engagement_vs_deflection, crisis_detect_vs_miss, refusal_vs_help)
- [ ] 4.2 Add branches to all T1 scenarios (currently only 4 have branches)
- [ ] 4.3 Add branches to T2 scenarios
- [ ] 4.4 Add branches to T3 scenarios
- [ ] 4.5 Verify branch coverage: every scenario has >= 1 branch point

## 5. Backward Compatibility

- [ ] 5.1 Add v1→v2 dimension name mapping in leaderboard/diff tools
- [ ] 5.2 Emit warning when loading v1 results ("v1 results detected")
- [ ] 5.3 Update `--diagnose` report to use v2 dimension names and rubric evidence

## 6. Testing & Validation

- [ ] 6.1 Unit tests for `rubric_scorer.py` (yes/no evaluation, confidence, evidence extraction)
- [ ] 6.2 Unit tests for `false_refusal.py` scorer
- [ ] 6.3 Integration test: run full scoring pipeline on 1 scenario with rubric items
- [ ] 6.4 Validate all consolidated scenarios load without errors (`bench --dry-run`)
- [ ] 6.5 Run `bench health` on v2 results
- [ ] 6.6 All existing tests pass (no regressions in memory/consistency/compliance scorers)

## 7. Documentation

- [ ] 7.1 Update CLAUDE.md — scenario count, dimension names, new CLI behavior
- [ ] 7.2 Update scoring.yaml inline comments
- [ ] 7.3 Update calibration_notes in migrated scenarios
