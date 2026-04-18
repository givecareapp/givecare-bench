# Internal implementation wiki

Reference notes for external repos and implementation patterns that GiveCare Bench
adapts internally.

These pages are intentionally practical:

- what the upstream repo does
- what we borrowed
- what we changed
- where the local implementation lives
- what assumptions are safe vs unsafe

## Pages

- `internal/wiki/llm-as-a-verifier.md` — upstream verifier framework and our single-trace transcript adaptation
- `internal/wiki/autoresearch.md` — upstream autoresearch loop and our scenario-optimization adaptation

## Scope

This wiki is internal reference material.

It is **not** the public benchmark contract and should not be cited as public
methodology without checking the canonical public docs under `docs/`.

## Update rule

Update these pages when any of the following change materially:

- the local file layout for verifier or autoresearch
- the evaluator / aggregation logic
- the human-calibration workflow
- the promotion / keep-discard criteria
- the upstream repo we consider the main inspiration
