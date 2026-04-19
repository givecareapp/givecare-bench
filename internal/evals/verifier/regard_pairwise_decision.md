# Regard pairwise calibration decision

Status: approved as a calibration layer, not approved as a production ranking layer
Updated: 2026-04-17

## Decision

Use pairwise / best-worst comparisons as a **secondary calibration method** for
regard, especially on the pass-only slice.

Do **not** replace the main absolute axis labels with pairwise data yet.

## Why

Absolute labels are still needed for:

- interpretable audits
- quote-backed scorer diagnostics
- per-axis regression tests
- public methodology explanations

Pairwise comparisons are useful because they may be more stable for:

- subtle grounding differences
- autonomy / directive-tone tradeoffs
- dependency-colored closers among otherwise decent responses

## Current policy

1. keep `pass|mixed|fail` axis labels as the main scorer target
2. collect a small same-scenario pairwise pilot on clean traces
3. compare pairwise outcomes against absolute human labels and scorer outputs
4. only consider ranking-layer use if pairwise labels show better stability and better alignment with held-out human judgment

## Promotion condition

Do not feed pairwise-derived quality adjustments into the public leaderboard
until they have been measured on a held-out validation set and documented in the
methodology notes.
