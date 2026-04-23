# Benchmark status follow-up — 2026-04-22

Supersedes the "holdout is future work" framing in
`benchmark_status_memo_2026-04-17.md §3.2`. Does not edit that memo; this is
the point-in-time correction.

## What changed since 2026-04-17

### Holdout labels landed

- Annotator A: 35 traces (completed before 2026-04-20)
- Annotator B: 35 traces (completed before 2026-04-20)
- Conflict resolution: 8 disputes adjudicated 2026-04-20 (see
  `quality_holdout/conflict_resolution.md`, `iaa_memo.md`)

### Holdout gold merged

- Script: `scripts/build_holdout_gold.py`
- Output: `internal/evals/verifier/quality_holdout/labels/gold/` (35 files)
- Summary: `internal/evals/verifier/quality_holdout/gold_resolution_summary.md`
- Composition: 27 A+B-agreed + 8 adjudicated
- Public layer: 11 hard fails / 24 pass

### Promotion gate pre-registered

- Doc: `internal/evals/verifier/quality_layer_promotion_gate.md`
- Five clauses (G1–G5) with machine-readable thresholds
- Covers: no-regress on gold public layer, holdout public-layer accuracy,
  non-degenerate regard label distribution, non-negative pass-only Pearson r
  on both reference sets, no catastrophic gold exact-match collapse

### Leaderboard metadata reconciled (Phase A)

- Script: `scripts/reconcile_leaderboard_metadata.py`
- The stale "Regard v2 deployed" claim in
  `data/leaderboard/leaderboard.json` has been retired; the runtime scorer
  saturates to pass on every regard axis and Regard v2 was reverted on
  2026-04-17.
- `quality_layer.status` remains `calibrated-diagnostic`; holdout block now
  reflects the merged gold and pending audits.

## What is still pending

- `scripts/audit_holdout_regard.py` — emit
  `current_regard_vs_holdout.md` + `.csv`
- `scripts/audit_holdout_scorer.py` — emit
  `current_scorer_vs_holdout.md` + `.csv`
- Scorer iteration loop — grounded in the known failure modes:
  grounding saturation, CBT-thought-record template FN, dose-splitting FN,
  false-privacy implied-promise FN
- Rescore (second pass, post-regard-fix, distinct from the 2026-04-18 rescore
  which aligned the public layer only)
- Leaderboard metadata reconcile (Phase B, post-gate)

## Framing for external communication

Rescoring frozen transcripts is a clean scorer A/B: model outputs are held
fixed, only the evaluator varies. Rank deltas are attributable to scorer
change and not confounded by model nondeterminism.

When the gate clears, the scoped claim is:

> "v2.0 leaderboard: same frozen 15-model transcript corpus, rescored under a
> regard scorer tuned on the 60-trace gold dev set and independently validated
> on a 35-trace held-out human-labeled quality set (95 traces total). Public
> hard-fail layer preserved at 60/60."

Explicit non-claims:

- not "universally calibrated regard" — scoped to the 95-trace reference set
- not portable to models outside the frozen 15 — new entrants need fresh
  transcripts under the same harness before rescoring
- the holdout is specifically the *independence* story (not tuned on) — that
  is what makes the v2.0 claim defensible
