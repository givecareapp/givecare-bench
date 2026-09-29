# Quickstart

Type: how-to.

Install the project with uv. Set the provider key for transcripts and the TypeSafe
key for judging. Scenarios with judge-decided branches also call TypeSafe during
generation, so a live run needs both keys and both hosts (`openrouter.ai` and
`api.typesafe.ai`); generation refuses to start without the judge key. Plan paid
work before running it. Credential presence does not prove network access.
From the same execution environment, check DNS/TLS/HTTP reachability to both
hosts before requesting pilot approval:

```bash
curl -A 'OpenAI File Downloader, XaiImageApiFetch/1.0' --head --max-time 20 https://openrouter.ai/
curl -A 'OpenAI File Downloader, XaiImageApiFetch/1.0' --head --max-time 20 https://api.typesafe.ai/
```

An HTTP response proves only that this endpoint responded. A 401, 403, or proxy
failure still needs investigation. A successful root request does not prove that
authenticated inference will work. Establish that with the approved small pilot,
then inspect its saved responses before a broader run.

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
Each model also owns an optional `endpoint`: the exact OpenRouter provider slug.
A named endpoint sends `only: [endpoint]` with `allow_fallbacks: false`. An absent
endpoint explicitly measures the **routed service**, with fallbacks allowed.
Both modes require support for the supplied generation parameters. The dry run
prints the policy. The manifest freezes it per model under
`transcript_policy.serving`, and the same provider object enters each journaled
request. Actual returned providers remain in transcript metadata and the summary.
Verify endpoint availability and prices before selecting one. A base provider
slug can match multiple variants or regions. For an endpoint-specific study,
verify and select the full endpoint slug. A restriction alone does not establish
an immutable endpoint. Never infer a single-provider comparison from a model name.

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
<run-id>` orders observation families by affected unresolved judgments, then raw
unresolved rate. Use `bench --json questions <run-id>` for exact conversation,
turn, bound observation, and possible-verdict references.
`bench compare --old <run-id> --new <new-run-id>` reports transitions,
applicability, coverage, uncertainty, and cost on unchanged transcript bytes.
Add `--expectations <file.jsonl>` to report agreement with frozen expectations.
Follow [Evaluator validation](validation.md) before interpreting that agreement
as accuracy.
The new bundle retains source files under `inputs/<source-hash>/`. Keep those
relative paths intact. They are part of the frozen plan.

Planning groups questions by identical evidence and splits groups against the
judge's estimated context limits. Every resulting request is checked again before
dispatch. A single observation whose evidence exceeds the limit is rejected;
evidence is never truncated or summarized. Long conversations can still exceed
that single-observation limit.

Judge requests follow the same recovery contract as target generation. Each
request is recorded in `attempts.jsonl` before dispatch. Its answer is flushed
to `answers.jsonl` before the next request. Judgments are derived from those
answers, not saved separately per request. Repeat the `bench scan run` command
to resume unfinished judging. Request identity includes the conversation, role,
turn, and exact input hash, so completed requests within a turn are retained.

Use a source checkout with the engine version recorded in a historical scan
plan to replay that scan. Keep its bundle unchanged. New judging requires a new
plan and cost approval; old plans are not migrated to the current request format.

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

Separate model runs may share a publication when their code and common generation
settings match. Each model must have one recorded, consistent serving policy.
Different policies for the same model are rejected, not merged into one row.
Missing scenario coverage remains a separate publication error.

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
The current schemas are `safety-care/v4` and `gc-bench.web-benchmark-release/v4`.
Deploy the owner documentation before the matching website consumer. Do not sync
new releases into a consumer that still accepts the previous schema.

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
