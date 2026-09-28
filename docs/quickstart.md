# Quickstart

Type: how-to.

Install the project with uv. Set the provider key for transcripts and the TypeSafe
key for judging. Plan paid work before running it.

```bash
uv sync --extra dev
export OPENROUTER_API_KEY=...
export TYPESAFE_API_KEY=...
uv run bench -m <catalog-model-id> --dry-run
uv run bench -m <catalog-model-id> -y --max-cost-usd <budget>
```

Select a model from `src/invisiblebench/models/config.py`. Add a new model there
with verified provider prices before planning it. Unknown IDs are rejected;
the CLI does not invent prices. The selected prices drive both estimation and
dispatch accounting and are saved as `model_pricing` in `run_manifest.json`.
Reservations are estimates, not an absolute billing guarantee. Provider usage
can exceed them. Cost ceilings and prices must be finite and non-negative.

The transcript run writes to `results/<run-id>/`. The run ID is a UTC timestamp
in `YYYY-MM-DD_HH-MM-SSZ` form. Model identity stays in the manifest and Jury Card.
Each new run has its own directory, including repeated runs of the same model.
To resume generation, repeat the same command with `--output results/<run-id>`
and the total approved ceiling, not an additional budget. Saved costs count
against that ceiling. The model roster, prices, scenario bytes, generation policy,
source code, and lockfile must match. Runs created before generation journals
were added cannot resume. A run with a scan plan cannot resume generation.

`generation/*.jsonl` retains each target attempt and response, including empty
responses and paid branch decisions. Records are flushed and synced before the
next call. Completed calls are replayed, not purchased again. `transcripts/`
is derived from those records after each scenario completes.

A timeout, cancellation during dispatch, malformed response, or incomplete record
stops automatic resume: a missing response does not prove there was no charge.
A saved response with unknown cost also stops generation and automatic resume.
Keep the run intact and reconcile with the provider before approving a new run.
Only a budget refusal before dispatch can retry automatically on resume.
Target HTTP calls have no hidden retries. Empty responses retain the bounded
retry policy saved in the manifest.
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
├── attempts.jsonl       # each judge request, recorded before dispatch
├── answers.jsonl        # one saved record per judge request (probabilities, cost)
├── judgments.jsonl      # one verdict per conversation and check, derived from answers.jsonl
├── run_manifest.json
├── transcript_run.json
├── generation/          # target attempts and responses; generation recovery source
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

Every planned request is checked for estimated context limits before dispatch.
Requests that remain oversized are rejected; evidence is not truncated or summarized.
Long crisis conversations can exceed these limits. Requests are not split automatically.

Judge requests follow the same recovery contract as target generation. Each
request is recorded in `attempts.jsonl` before dispatch. Its answer is flushed
to `answers.jsonl` before the next request. Judgments are derived from those
answers, not saved separately per request. Repeat the `bench scan run` command
to resume unfinished judging.

Resume retries a request only when its outcome and cost are known: a budget
refusal before dispatch, or an invalid answer with reported usage. Any error
after dispatch leaves the outcome unknown: an interruption, timeout, dropped
connection, HTTP error, or an answer without reported usage. It stops automatic
resume, because a missing answer does not prove there was no charge. A partial
scan without an attempt journal also cannot resume. Keep the blocked bundle
for inspection. To continue, plan a new scan from the retained transcript run:

```bash
uv run bench scan plan results/<run-id> --output results/<new-run-id>
```

Planning makes no paid calls. Review the estimate before `bench scan run`.
Valid `UNCLEAR` decisions are complete.
Move the entire bundle to retain replay.

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

The public contract is `.givecare/module.json`. Its single capability points at
the packaged `invisiblebench.projection` module, a plain script. It writes only
`data/leaderboard/leaderboard.json` and the web release archive.
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
