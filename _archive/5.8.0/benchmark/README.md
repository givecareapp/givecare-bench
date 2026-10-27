# Benchmark data

Type: reference.

This directory contains the public benchmark contract.

- `benchmark_inventory.json` is the source of truth for corpus version and
  inventory.
- `benchmark_card.json` describes intended use and limits.
- `../src/invisiblebench/models/scan.py` defines the scan contract.
  `../src/invisiblebench/scoring.py` derives the public projection.
- `scenarios/` contains the public scenarios. `models/scenario.py` in the runtime
  owns validation; `scenarios/SCENARIO_SCHEMA.yaml` is its generated JSON Schema.
  A scenario is the caregiver script; check YAML is the only rubric. Branches,
  sessions, persona context, and provenance are retained.
- `tests/` proves the runtime and artifact contract.

The runtime lives in `src/invisiblebench/`. See the [method](../docs/methodology.md).
Use the JSON inventory and scoring contract for current counts, versions, and
fields.

Private holdout scenarios are loaded from an external directory. Do not add
private scenario text, expected answers, or judge prompts to public artifacts.
