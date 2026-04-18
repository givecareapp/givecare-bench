# Internal surfaces

This directory holds active internal workflows that support the benchmark but are not part of the public benchmark contract.

## Directories

- `autoresearch/`: scenario optimization campaigns, scout analysis, and autoresearch-style keep/discard loops for single-scenario benchmark tuning
- `evals/`: scorer validation, error analysis, and labeling assets (validation **in progress**; all judges unvalidated or fixed-unvalidated)
- `wiki/`: internal implementation reference notes for upstream inspirations and local adaptations
- `papers/`: paper source and research artifacts

## Policy

- `internal/` is versioned because it is operationally useful.
- `internal/` is not part of the public leaderboard contract.
- Superseded internal plans, remediation bundles, and one-off artifacts should move to `archive/internal/`.
- Results or claims generated from `internal/` work should not be presented as public benchmark leaderboard results unless they are explicitly promoted into the public benchmark surface.
