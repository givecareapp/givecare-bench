# Benchmark data

This directory is the public benchmark contract.

The scoring model is `safety-care/v1`: two layers reported side by side, never composited and never ranked. **Safety** — 4 lines (Crisis, Scope, Identity, Autonomy) as per-line violation rates (claim-bearing only for `claim_ready` checks, currently empty). **Care** — 5 qualities (Belonging, Attunement, Trauma-awareness, Relational, Advocacy) as directional/`not_claim_ready` distributions. There is no `overall_score`. Canonical model: [ontology](../docs/ontology.md); see also [methodology](../docs/methodology.md) and [taxonomy](../docs/taxonomy.md).

It contains:
- `benchmark_inventory.json`: source of truth for benchmark counts/version
- `benchmark_card.json`: public benchmark card
- `configs/`: scoring config, prompts, and jurisdiction rules
- `scenarios/`: active public scenario corpus only
- `tests/`: benchmark tests

It does not contain the runtime package anymore. Runtime code now lives in `src/invisiblebench/`.

## Public contract

- benchmark version: `4.0.0` (canonical source: `benchmark_inventory.json`)
- public scope: benchmark core only
- public harness: `llm/raw`
- public scenarios: `63`
- checks: `50` (35 direct-LLM routes, 10 regex-first with conditional LLM review, 5 no-LLM rules)

## Notes

- private confidential holdouts are loaded from `INVISIBLEBENCH_PRIVATE_CONFIDENTIAL_SCENARIOS_DIR` and are not stored here.
