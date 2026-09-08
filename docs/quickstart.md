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
uv run python scripts/run_scan.py results/run_<id> \
  --dry-run --llm-model openai/gpt-5-mini
uv run python scripts/run_scan.py results/run_<id> \
  --plan <scan-dir>/scan_plan.json \
  --max-cost-usd <budget> --llm-model openai/gpt-5-mini
```

Inspect evidence with:

```bash
uv run bench explain your-org/your-model <scenario-id> --failures \
  --scan <scan-dir>/per_run.jsonl
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
uv run python scripts/generate_leaderboard.py --input <scan-dir>/per_run.jsonl
uv run python scripts/qa_leaderboard.py --scan <scan-dir>/per_run.jsonl \
  --leaderboard <scan-dir>/leaderboard.candidate.json --strict
```

Use the [owner projection operation](evidence-lane.md) to create release files.
The generator cannot write the canonical leaderboard.

After a refactor, replay a frozen current-contract scan without API calls:

```bash
uv run python scripts/rescore_diff.py --frozen <scan-dir>/per_run.jsonl
```

Replay checks the request, parsing, evidence, and aggregation. It does not rerun
model inference. A scan from a retired contract requires a new benchmark run.
