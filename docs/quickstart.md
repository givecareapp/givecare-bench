# Quickstart

Install the project with uv. Set a provider key. Plan paid work before running it.

```bash
uv sync --extra dev
export OPENROUTER_API_KEY=...
uv run bench -m your-org/your-model --dry-run
uv run bench -m your-org/your-model -y --max-cost-usd <budget>
```

The transcript run writes to `results/<run-id>/`. The run ID is a UTC timestamp
in `YYYY-MM-DD_HH-MM-SSZ` form. Model identity stays in the manifest and Jury Card.
Each new run has its own directory, including repeated runs of the same model.
The CLI refuses to overwrite an existing run.
Card titles show the model name and a readable UTC date and time.

Create a dry-run scan plan in the same directory, then run it with an explicit ceiling:

```bash
uv run python scripts/run_scan.py plan results/<run-id> \
  --llm-model openai/gpt-5-mini
uv run python scripts/run_scan.py run \
  --plan results/<run-id>/scan_plan.json --max-cost-usd <budget>
```

The bundle contains all inputs needed for a scan and replay:

```text
results/<run-id>/
├── jury-card.md         # standard report, written when judging completes
├── scan_plan.json       # frozen checks, judge settings, and input hashes
├── judgments.jsonl     # one saved record per completed request
├── run_manifest.json
├── transcript_run.json
└── transcripts/
```

The Jury Card and evidence bundle are the two logical artifacts. There is no
separate per-run narrative report or scorecard export. The public leaderboard
is a shared projection across runs.

To judge existing responses under a new plan, pass `--output results/<new-run-id>`.
The new bundle retains source files under `inputs/<source-hash>/`. Keep those
relative paths intact. They are part of the frozen plan.

Each judgment is flushed to disk before the next request. Repeat the run
command to resume unfinished work. A technical error is saved and stops the
scan. Resume retries that unfinished request. Valid `UNCLEAR` decisions are
complete. Move the entire bundle to retain replay.

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

Run the proof checks before sharing an artifact:

```bash
uv run ruff check .
uv run pytest benchmark/tests -q
uv run python scripts/lint_turn_indices.py --strict
```

The scan can contain `UNCLEAR`. It remains evidence and does not start a second resolution pipeline.

After a refactor, replay a frozen current-contract scan without API calls:

```bash
uv run python scripts/rescore_diff.py --frozen <scan-dir>
```

Replay checks the request, parsing, and evidence. It does not rerun
model inference. A scan from a retired contract requires a new benchmark run.
