# Quickstart

Install the project with uv. Set a provider key. Plan paid work before running it.

```bash
uv sync --extra dev
export OPENROUTER_API_KEY=...
uv run bench -m your-org/your-model --dry-run
uv run bench -m your-org/your-model -y --max-cost-usd <budget>
```

The transcript run writes under `results/`. Create a dry-run scan plan, then
run the same source with that plan and an explicit ceiling:

```bash
uv run python scripts/run_scan.py plan results/run_<id> \
  --output <scan-dir> --llm-model openai/gpt-5-mini
uv run python scripts/run_scan.py run \
  --plan <scan-dir>/scan_plan.json --max-cost-usd <budget>
```

The bundle contains all inputs needed for a scan and replay:

```text
<scan-dir>/
├── scan_plan.json       # frozen checks, judge settings, and input hashes
├── judgments.jsonl     # one saved record per completed request
└── inputs/<source-hash>/
    ├── run_manifest.json
    ├── transcript_run.json
    └── transcripts/
```

Each judgment is flushed to disk before the next request. Repeat the run
command to resume unfinished work. A technical error is saved and stops the
scan. Resume retries that unfinished request. Valid `UNCLEAR` decisions are
complete. Move the entire bundle to retain replay.

Inspect evidence with:

```bash
uv run bench explain your-org/your-model <scenario-id> --failures \
  --scan <scan-dir>
```

Run the proof checks before sharing an artifact:

```bash
uv run ruff check .
uv run pytest benchmark/tests -q
uv run python scripts/lint_turn_indices.py --strict
```

The scan can contain `UNCLEAR`. It remains evidence and does not start a second resolution pipeline.

Generate a private score candidate and check it:

```bash
uv run python scripts/generate_leaderboard.py --scan <scan-dir>
uv run python scripts/qa_leaderboard.py --scan <scan-dir> \
  --leaderboard <scan-dir>/leaderboard.candidate.json
```

Use the [owner projection operation](evidence-lane.md) to create release files.
The generator cannot write the canonical leaderboard.

After a refactor, replay a frozen current-contract scan without API calls:

```bash
uv run python scripts/rescore_diff.py --frozen <scan-dir>
```

Replay checks the request, parsing, and evidence. It does not rerun
model inference. A scan from a retired contract requires a new benchmark run.
