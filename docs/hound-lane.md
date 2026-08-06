# Hound Owner Lane

Hound owns two bounded writes in `gc-bench`.

## Evals intake

First materialize one exact verified Evals owner projection. This is the only
cross-repository read. It writes fixed local bytes and a provenance receipt.

```bash
python3 scripts/sync_evals_projection.py \
  --run-dir ../gc-evals/.hound/runs/<exact-plan-id>
uv run python scripts/intake/import_evals.py \
  --selected-id <eval-record-id> --output /tmp/gc-bench-candidate.json
```

The compiler and Hound driver read only
`data/imports/evals/materialization.json`. This one atomically replaced file
contains the exact source bytes and their verified Hound receipt. A process
stop cannot expose a payload from one generation with a receipt from another.

The receipt stores the verified source run ID and ArtifactRef. A candidate input
contains only one selected ID. Hound adds that receipt to the promoted scenario
metadata. It never reads `gc-evals` during candidate planning or execution.

## Public web release

Owner-native release builders write only fixed owner source paths. Their current
v4 source bytes were moved once from the former direct web release.

```bash
uv run python delivery/build_public_transcript_release.py \
  --source model/id=results/run_... --release-version v4.0.0
uv run python delivery/build_public_score_release.py \
  --input <release>/per_run.jsonl --release-version v4.0.0
```

`data/publication-source/web-bench/` owns the complete source set:

- `current-evidence.json`
- `evidence/v4.0.0/manifest.json` and its four model files
- `scores/v4.0.0/manifest.json` and its four model files

Create a Hound project input that binds the canonical leaderboard, strict QA
stamp, `current-evidence.json`, and both source manifests by SHA-256.

```json
{
  "schema_version": "gc-bench.web-benchmark-release.input/v1",
  "leaderboard_path": "data/leaderboard/leaderboard.json",
  "leaderboard_sha256": "<sha256>",
  "qa_stamp_path": "data/leaderboard/.qa-stamp",
  "qa_stamp_sha256": "<sha256>",
  "current_evidence_path": "data/publication-source/web-bench/current-evidence.json",
  "current_evidence_sha256": "<sha256>",
  "evidence_manifest_path": "data/publication-source/web-bench/evidence/v4.0.0/manifest.json",
  "evidence_manifest_sha256": "<sha256>",
  "scores_manifest_path": "data/publication-source/web-bench/scores/v4.0.0/manifest.json",
  "scores_manifest_sha256": "<sha256>"
}
```

`corpus.project` validates every source member, the cross-file counts, model
IDs, corpus hash, scoring provenance, and strict QA. It emits one deterministic
public ArtifactRef:

```text
owner: bench.publish
kind: owner-projection
artifact_id: data/releases/web-bench-release.tar.gz
```

The archive has exactly 13 regular files: `release-manifest.json` plus
`leaderboard.json`, `current-evidence.json`, five evidence files, and five
score files. The release manifest schema is `gc-bench.web-benchmark-release/v1`.
Consumers verify and atomically materialize this one archive. There is no
direct `gc-bench` write into a consumer repository.
