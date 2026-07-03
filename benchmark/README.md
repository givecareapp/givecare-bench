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

- benchmark version: `3.1.0` (canonical counts/version: `benchmark_inventory.json` + `CLAUDE.md` — do not hardcode elsewhere)
- public scope: benchmark core only
- public harness: `llm/raw`
- public scenarios: `63` in the checked-in Phase 2 artifact; `63` on disk and included by the next live `--full` run
- checks: `50` (46 LLM-judged, 4 deterministic)

## Notes

- `archive/scenarios/` contains historical and system-only scenario material.
- private confidential holdouts are loaded from `INVISIBLEBENCH_PRIVATE_CONFIDENTIAL_SCENARIOS_DIR` and are not stored here.
