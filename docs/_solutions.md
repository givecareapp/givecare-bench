# Solutions Log

Diátaxis: reference

## Scoring comparability now uses prompt-template hashes, and scenario rubric contracts are fully supported

**Date**: 2026-03-29  
**Files**: `src/invisiblebench/api/client.py`, `src/invisiblebench/evaluation/scorers/{safety,compliance,regard,coordination,rubric_scorer}.py`, `src/invisiblebench/models/{__init__,scenario}.py`, `src/invisiblebench/loaders/scenario_loader.py`, `benchmark/configs/scoring.yaml`, `benchmark/configs/prompts/compliance_framework.txt`, `benchmark/scenarios/SCENARIO_SCHEMA.yaml`

Run audit comparability was incorrectly using hashes of fully rendered judge prompts, which made scenario-specific prompt content look like contract drift. At the same time, the scenario contract had drifted: `rubric` / `autofail_rubric` were authored in scenario JSON, but typed models and rubric scoring only partially supported them, and ordinal `rubric_criteria` were being flattened into binary behavior.

**Fix**: judge metadata now stores stable prompt-template hashes for comparability; the compliance contract explicitly hard-fails false scope/capability claims and preserves allowed practical caregiving support plus general public medication information; scenario models and validation now preserve `rubric`, `autofail_rubric`, and ordinal `rubric_criteria`; and the rubric scorer now handles ordinal criteria with partial credit instead of silently degrading them.
