# Benchmark data

This directory contains the public benchmark contract.

- `benchmark_inventory.json` is the source of truth for corpus version and
  inventory.
- `benchmark_card.json` describes intended use and limits.
- `../src/invisiblebench/models/scan.py` defines the scan contract.
  `../src/invisiblebench/scoring.py` derives the public projection.
- `scenarios/` contains the public scenario corpus and schema.
- `tests/` proves the runtime and artifact contract.

The runtime package lives in `src/invisiblebench/`. The active scan path uses
one LLM judge per active check. It appends each decision to `judgments.jsonl`.
`NOT_APPLICABLE` is an explicit verdict.

`PASS`, `FAIL`, `UNCLEAR`, and `NOT_APPLICABLE` are the machine verdicts. A
`FAIL` needs transcript evidence. `UNCLEAR` stays visible. Optional critique
stays outside the ledger. It cannot change a verdict or block a scan or projection.

Safety and Care remain separate. The projection has no composite score or
model rank. Use the JSON inventory and scoring contract for current counts,
versions, and fields.

Private holdout scenarios are loaded from an external directory. Do not add
private scenario text, expected answers, or judge prompts to public artifacts.
