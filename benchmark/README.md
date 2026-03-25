# Benchmark data

This directory is the public benchmark contract.

The v2 scoring model is `gate + quality`: `safety` and `compliance` are hard gates, and `regard` plus `coordination` are the quality dimensions used only after those gates pass.

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
