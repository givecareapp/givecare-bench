# GiveCare Bench automation

This file describes read-only harvest and watch work. It does not run paid
scans and it does not write to another repository or service.

## Read-only harvest

Use the `bench` CLI to inspect committed benchmark artifacts:

```bash
uv run bench --json leaderboard status
uv run bench --json health
uv run bench --json runs --limit 25
uv run bench --json get <run-id>
uv run bench --json explain <model> <scenario> --failures
```

Harvest only a verified, newer publication with present source artifacts. If
the current leaderboard is historical or its declared artifact is missing,
report `NOTHING_TO_HARVEST` and write nothing.

A harvest digest may carry check IDs, verdict counts, and links to committed
artifacts. Keep scenario text, expected answers, judge prompts, private
transcripts, and credentials out of the digest. Drafts are
for owner review. Never send or publish them from this workflow.

## Release watch

`scripts/bench_watch.py --propose` reads the roster, benchmark inventory,
leaderboard metadata, and the public model catalog. It writes a dated proposal
under `delivery/watch/`. It does not run a scan, call a paid model, or emit a
task.

The owner decides whether a candidate is worth a scan. A paid scan must follow
the dry-run plan and explicit `--max-cost-usd` contract in
[`docs/quickstart.md`](docs/quickstart.md).

## Publication boundary

The publication operation reads a private candidate input that binds a scan
path and hash to a leaderboard path and hash. Strict QA runs at plan and
execute time. The deterministic `corpus.project` operation writes the
canonical owner projection and release archive. Private conversations and
judge decisions stay private.

`corpus.apply` promotes candidate scenario content. It does not review or
change model verdicts. Optional critique is result metadata and cannot block a
scan or publication.

## Safety rules

- Keep Safety and Care separate.
- Do not create a composite score or model rank.
- Keep `UNCLEAR` visible.
- Do not copy private benchmark material into `gc-sms` or public releases.
- Do not send messages, deploy, or change services from this workflow.
