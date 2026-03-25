# GiveCare Bench docs

GiveCare Bench is a standalone public benchmark repo with a deliberate split between public benchmark surfaces and internal evaluation work.

## Public benchmark surface

These directories define the public benchmark product:
- `benchmark/` — public corpus, configs, contract, tests
- `src/invisiblebench/` — runtime package
- `scripts/` — active utilities
- `docs/` — public docs
- `data/leaderboard/` — generated artifacts

This is the surface that external users should use to:
- inspect the public corpus
- run the raw-model benchmark
- inspect the scoring contract
- generate leaderboard artifacts

## Internal-active surface

These directories are active but non-public-facing:
- `internal/` — active non-public (autoresearch, evals, papers)

They exist to support:
- scenario optimization
- judge validation
- internal research and publication work

They are not part of the public leaderboard contract.

## Other directories

- `adapters/` — external bridge assets
- `archive/` — historical material

If you are trying to use the benchmark, start with the public surface, not `internal/` or `archive/`.
