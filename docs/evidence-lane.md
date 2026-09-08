# Helm Evidence owner lane

`gc-bench` declares two bounded Evidence operations.

- `corpus.apply` stages candidate scenario content. It is a content provenance gate. It does not validate or change model verdicts.
- `corpus.project` creates the deterministic owner projection from a private
  candidate input. The input binds a scan path and SHA-256 to a leaderboard
  path and SHA-256. It does not run a judge.

The driver is `evidence-driver.json`. Check it with:

```bash
helm evidence driver check --driver evidence-driver.json
```

Keep scenario text, judge prompts, expected answers, private traces, and credentials out of consumer repositories and public releases. Consumers read the committed owner projection.

The project input uses `gc-bench.web-benchmark-release.input/v2`. The public
release contains the safe aggregate leaderboard and a manifest. Private
conversations and model decisions remain in protected evidence storage.
