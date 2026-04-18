# Rescored benchmark summary — 2026-03-31

## Plain-language summary

We reviewed the benchmark on a frozen set of transcripts and confirmed that one compliance rule was too broad.

That rule was incorrectly hard-failing many answers that were actually doing the right thing, including:
- honest AI disclosure
- honest statements about not controlling deletion
- honest statements about uncertainty around memory/platform behavior
- healthy anti-dependency boundaries

We repaired that scorer family, added regression tests, and rescored the frozen corpus.

## What changed after rescoring

Across the full 15-model board (`750` rows):

- hard-fail rows dropped from `261` to `119`
- mean overall score rose from `0.539` to `0.690`

This confirms that the original leaderboard was being materially distorted by an over-broad scope/capability rule.

## What we now believe

- The benchmark is still useful and worth continuing.
- The earlier board should be treated as provisional/diagnostic, not final ground truth.
- The rescored board is a better representation of model behavior on the frozen corpus.
- Some disputed scenario families still need careful interpretation before any strong public claims.

## Biggest implications

The rescored board changes rank order materially.
The largest upward moves are:
- `GPT-5.4`: `7 -> 1`
- `Claude Opus 4.6`: `12 -> 2`
- `Claude Sonnet 4.5`: `11 -> 3`

The largest scenario-family repairs include:
- `tier1_scope_honesty_001`
- `tier2_attachment_001`
- `tier3_longitudinal_001`
- `context_regulatory_therapy_function_001`
- `context_regulatory_misrepresentation_001`

## What this is not

This was **not** a fresh benchmark run.
We did **not** regenerate model conversations.

This was a rescoring pass on the same frozen transcripts, which makes the before/after comparison much more trustworthy.

## Next steps

- regenerate public leaderboard artifacts from the rescored outputs
- finish the remaining verifier review on residual disputed slices
- publish the rescored board with clear caveats about what changed and why
