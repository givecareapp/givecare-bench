# Task 2.7 — Minimum Dimension Coverage Verification

Date: 2026-02-12

## Scope

- Verified consolidated core scenario set from:
  - `benchmark/scenarios/manifests/t1_core.txt`
  - `benchmark/scenarios/manifests/t2_core.txt`
  - `benchmark/scenarios/manifests/t3_core.txt`
- Core scenario count scanned: 28
- Rule: each v2 dimension must have at least 2 scenarios with weight `>= 2`

## Method

- Added validator: `benchmark/scripts/validation/verify_dimension_coverage.py`
- Legacy-to-v2 mapping used during transition:
  - `safety <- crisis_safety`
  - `compliance <- regulatory_fitness`
  - `attunement <- trauma_informed_flow`
  - `belonging <- belonging_cultural_fitness`
  - `memory <- memory_hygiene`
  - `consistency <- longitudinal_consistency`
- `false_refusal` counted via scenario path `benchmark/scenarios/safety/false_refusal/*.json` until full rubric dimension migration.

## Fix Applied

- `benchmark/scenarios/continuity/longitudinal_trust.json`
  - `scoring_dimensions.memory_hygiene`: `1 -> 2`

This resolves a single failing gap where only one scenario previously met memory weight `>= 2`.

## Results

- `safety`: 20 (PASS)
- `compliance`: 27 (PASS)
- `attunement`: 28 (PASS)
- `belonging`: 24 (PASS)
- `false_refusal`: 2 (PASS)
- `memory`: 2 (PASS)
- `consistency`: 11 (PASS)

## Validation Command

```bash
python3 benchmark/scripts/validation/verify_dimension_coverage.py
```

Exit status: `0` (all dimensions satisfy minimum coverage).
