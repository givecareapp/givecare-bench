# Quickstart

Type: how-to.

Install the project with uv. Set the provider key for transcripts and the TypeSafe
key for judging. Plan paid work before running it.

```bash
uv sync --extra dev
export OPENROUTER_API_KEY=...
export TYPESAFE_API_KEY=...
uv run bench -m your-org/your-model --dry-run
uv run bench -m your-org/your-model -y --max-cost-usd <budget>
```

The transcript run writes to `results/<run-id>/`. The run ID is a UTC timestamp
in `YYYY-MM-DD_HH-MM-SSZ` form. Model identity stays in the manifest and Jury Card.
Each new run has its own directory, including repeated runs of the same model.
The CLI refuses to overwrite an existing run.
Card titles show the model name and a readable UTC date and time.

Create a dry-run scan plan in the same directory, then run it with an explicit
ceiling. `--llm-model` defaults to the pinned judge model in
`src/invisiblebench/api/typesafe.py`:

```bash
uv run bench scan plan results/<run-id> \
  --llm-model <judge>
uv run bench scan run \
  --plan results/<run-id>/scan_plan.json --max-cost-usd <budget>
```

The bundle contains all inputs needed for a scan and replay:

```text
results/<run-id>/
├── jury-card.md         # standard report, written when judging completes
├── scan_plan.json       # frozen checks, questions, thresholds, and input hashes
├── answers.jsonl        # one saved record per judge request (probabilities, cost)
├── judgments.jsonl      # one verdict per conversation and check, derived from answers.jsonl
├── run_manifest.json
├── transcript_run.json
└── transcripts/
```

The Jury Card and evidence bundle are the two logical artifacts. There is no
separate per-run narrative report or scorecard export. The public leaderboard
is a shared projection across runs.

To plan a different judge against the exact frozen evidence, use:

```bash
uv run bench scan rejudge results/<run-id> --output results/<new-run-id> \
  --llm-model <judge>
```

Review the estimate, then execute with `bench scan run`. `bench questions
<run-id>` orders questions by unresolved rate. `bench compare --old <run-id>
--new <new-run-id>` compares two current-format scans without model calls.
A comparison measures agreement, not judge accuracy.
The new bundle retains source files under `inputs/<source-hash>/`. Keep those
relative paths intact. They are part of the frozen plan.

Each answer is flushed to `answers.jsonl` before the next request; judgments
are derived from those answers, not saved separately per request. Repeat the
run command to resume unfinished work. A technical error is saved and stops
the scan. Resume retries that unfinished request. Valid `UNCLEAR` decisions
are complete. Move the entire bundle to retain replay.

Inspect evidence with:

```bash
uv run bench explain your-org/your-model <scenario-id> --failures \
  --scan results/<run-id>
uv run bench runs
uv run bench get <run-id>
uv run bench jury <run-id>
```

`bench jury` regenerates the card without model calls. It preserves the marked
commentary section when the plan and ledger hashes still match. Put the author,
date, observation, and check or transcript-turn references in that section.
Notes do not change the judge's verdicts. The card and its quoted evidence stay
private. Archive complete run directories under `results/archive/`.

## Prepare a public projection

The public contract is `.givecare/module.json`. Its single capability declares
`.givecare/projection-driver.json`, whose native writer is the packaged
`invisiblebench.projection` module — a plain script, not an external runner.
Projection needs no provider key or private workspace adapter.

Generate and check a candidate from a complete current-contract scan:

```bash
uv run python scripts/generate_leaderboard.py --scan results/<run-id>
uv run python scripts/qa_leaderboard.py --scan results/<run-id> \
  --leaderboard results/<run-id>/leaderboard.candidate.json
```

Compute the projection first with `--dry-run` to inspect what would change:

```bash
uv run python -m invisiblebench.projection \
  --bundle results/<run-id> \
  --leaderboard results/<run-id>/leaderboard.candidate.json \
  --dry-run
```

The script binds the plan, judgments, and candidate leaderboard by SHA-256,
computed directly from the files at the given paths, and rejects a source run
that is incomplete, not current (mismatched benchmark, checks, or judge
settings), or has a dirty or missing `git_sha`. Changed inputs are re-hashed
on the next run automatically.

Inspect `expected_effects` in the dry-run output, then execute for real by
dropping `--dry-run`:

```bash
uv run python -m invisiblebench.projection \
  --bundle results/<run-id> \
  --leaderboard results/<run-id>/leaderboard.candidate.json
```

This replaces `data/leaderboard/leaderboard.json` and
`data/releases/web-bench-release.tar.gz` with an atomic, digest-verified write
(refuses symlinks, rolls back on partial failure). The archive contains only
the aggregate leaderboard and its member manifest. It excludes conversations,
judge answers, and private intake. Review and commit these outputs before a
consumer reads them by exact commit. This command does not push or deploy.

A contract update does not turn retained historical artifacts into results
under the current method. A consumer must check the release schema and version.

## Verify

Run the proof checks before sharing an artifact:

```bash
uv run ruff check .
uv run python scripts/check_examples.py verify
uv run pytest benchmark/tests -q
uv run python scripts/lint_turn_indices.py --strict
```

The scan can contain `UNCLEAR`. It remains evidence and does not start a second resolution pipeline.

After a refactor, replay a frozen current-contract scan without API calls:

```bash
uv run python scripts/rescore_diff.py --frozen <scan-dir>
```

Replay re-derives judgments from the frozen plan and the saved answers in
`answers.jsonl`. It does not call the judge model again. A scan from a
retired contract requires a new benchmark run.
