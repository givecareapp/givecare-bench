# Hound Owner Lane

Hound owns the two bounded repository writes in `gc-bench`.

Model generation and scoring scans stay direct owner operations. They already
have explicit cost plans, limits, checkpoints, and result contracts.

## Candidate intake

First run and verify the gc-evals Hound `corpus.project` capability. Then build
one bounded request from that exact public projection. The compiler verifies
the Hound run, the owner proof, the shared ArtifactRef, and the projection
digest. It does not read raw sibling split files. It does not stage candidates.

```bash
uv run python scripts/intake/import_evals.py \
  --source-plan-id <exact-plan-id> \
  --selected-id <eval-record-id> \
  --output /tmp/gc-bench-candidates.json
```

Review and execute the exact Hound plan.

```bash
hound plan --driver hound-driver.json \
  --operation corpus.apply \
  --input /tmp/gc-bench-candidates.json \
  --as-of YYYY-MM-DD \
  --output /tmp/gc-bench-candidate-plan.json
hound approve --plan /tmp/gc-bench-candidate-plan.json \
  --reviewer operator@example.com \
  --output /tmp/gc-bench-candidate-approval.json
hound execute --driver hound-driver.json \
  --plan /tmp/gc-bench-candidate-plan.json \
  --approval /tmp/gc-bench-candidate-approval.json
```

The request carries only the exact Evals Hound plan ID and exactly one selected
ID. One Hound plan can promote one scenario, so canonical truth cannot be left
partially updated. At both plan and execute, the Bench driver derives the fixed
Evals run path, asks the shared GiveCare primitive for its ArtifactRef, and
reads the exact verified owner projection. The plan binds that source, the
selected record, and its canonical `benchmark/scenarios` output digest. Human
approval of the exact plan is the promotion decision.
Hound apply is the only candidate-promotion writer. Review the resulting Git
diff before commit.

## Leaderboard projection

The explicit benchmark scan and strict-QA lane owns
`data/leaderboard/leaderboard.json` and `data/leaderboard/.qa-stamp`. Hound does
not run scans, generate the canonical leaderboard, or promote benchmark truth.

Create both owner files with the native owner commands:

```bash
uv run python scripts/generate_leaderboard.py \
  --input <scan>/per_run.jsonl --output data/leaderboard
uv run python scripts/qa_leaderboard.py \
  --scan <scan>/per_run.jsonl \
  --leaderboard data/leaderboard/leaderboard.json \
  --manual-adjudications <scan>/manual_adjudications.json --strict --stamp
```

`--stamp` is valid only with `--strict`. It atomically writes only the fixed
owner path `data/leaderboard/.qa-stamp`. It never publishes or writes a sibling.

Build one input that binds those two exact owner files. Add `learning_lineage`
only when a verified learning loop produced the canonical leaderboard.
The driver preserves its exact `demand_sha256`, `trace_refs`, and `module_refs`.
Scan-only releases omit this field. The driver never creates synthetic traces.

```json
{
  "schema_version": "gc-bench.leaderboard-projection.input/v1",
  "leaderboard_path": "data/leaderboard/leaderboard.json",
  "leaderboard_sha256": "<64 lowercase hex characters>",
  "qa_stamp_path": "data/leaderboard/.qa-stamp",
  "qa_stamp_sha256": "<64 lowercase hex characters>"
}
```

Run `hound plan`, `hound execute`, and `hound verify` for `corpus.project`.
The projection has no human gate because it can derive only deterministic
consumer bytes from exact strict-QA owner truth. It validates the stamp and the
leaderboard schema. It writes only this local owner projection:

- `data/leaderboard/leaderboard_web.json`

The Hound result binds both input digests and emits the exact
`givecare.artifact-ref/v1`. The reference identifies
`data/leaderboard/leaderboard_web.json` by content digest.
Commit the Hound-projected owner artifacts after review. Each consumer then
pulls that committed projection. `gc-bench` never writes into `gc-web`.
