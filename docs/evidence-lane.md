# Helm Evidence owner lane

`gc-bench` declares two bounded Evidence operations.

- `corpus.apply` stages candidate scenario content. It is a content provenance gate. It does not validate or change model verdicts.
- `corpus.project` creates the deterministic owner projection from a private
  candidate input. The input binds the bundle path, plan SHA-256, ledger
  SHA-256, candidate path, and candidate SHA-256. It does not run a judge.

The driver is `evidence-driver.json`. Check it with:

```bash
helm evidence driver check --driver evidence-driver.json
```

Keep scenario text, judge prompts, expected answers, private traces, and credentials out of consumer repositories and public releases. Consumers read the committed owner projection.

The project input uses `gc-bench.web-benchmark-release.input/v3`. The public
release contains the safe aggregate leaderboard and a manifest. Private
conversations and model decisions remain in protected evidence storage.

A project input has this exact shape. Hash the retained files after candidate generation.

```json
{
  "schema_version": "gc-bench.web-benchmark-release.input/v3",
  "bundle_path": "results/<run-id>",
  "plan_sha256": "<SHA-256 of scan_plan.json>",
  "judgments_sha256": "<SHA-256 of judgments.jsonl>",
  "leaderboard_path": "results/<run-id>/leaderboard.candidate.json",
  "leaderboard_sha256": "<SHA-256 of leaderboard.candidate.json>"
}
```

QA recomputes the exact public object from the ledger. Extra fields are errors.
Each model needs the complete current scenario roster and every active check.
Source runs must be complete and use the same clean code revision and transcript
policy. Plan, source, or ledger changes invalidate the bound hashes. Plan and
execute both run these checks.
