# Benchmark data

This directory is the public benchmark contract.

The scoring model is gate-then-quality. Safety (A) and compliance (B) are fail-closed gates; communication (C), coordination (D), and boundary integrity (F) are quality dimensions scored only after the gates pass. v3 adds 41 active verifier checks (48-mode failure registry) across all 5 dimensions, calibrated against human expert labels. See [methodology](../docs/methodology.md) and [taxonomy](../docs/taxonomy.md).

It contains:
- `benchmark_inventory.json`: source of truth for benchmark counts/version
- `benchmark_card.json`: public benchmark card
- `configs/`: scoring config, prompts, and jurisdiction rules
- `scenarios/`: active public scenario corpus only
- `tests/`: benchmark tests

It does not contain the runtime package anymore. Runtime code now lives in `src/invisiblebench/`.

## Public contract

- benchmark version: `2.1.0`
- public scope: benchmark core only
- public harness: `llm/raw`
- public scenarios: `50`
- branch-bearing files: `22`

## Notes

- `archive/scenarios/` contains historical and system-only scenario material.
- private confidential holdouts are loaded from `INVISIBLEBENCH_PRIVATE_CONFIDENTIAL_SCENARIOS_DIR` and are not stored here.
