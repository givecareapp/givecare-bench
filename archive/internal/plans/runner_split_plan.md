# Plan — split `src/invisiblebench/cli/runner.py` by subcommand

Status: **proposed, not started**
Owner: TBD
Prerequisites: tasks #11 (bench skill) and #12 (`--out` flag) done.

## Why

`src/invisiblebench/cli/runner.py` is 4045 LOC with 49 top-level defs/classes
and 21 subcommands. It is the single largest maintainability risk surfaced by
the review sweep. Top pains:

- Hard to review changes (diffs drown in unrelated context)
- Hard to type-check incrementally — one big module means one big mypy scope
- Hard for new contributors to find the code for a specific command
- Hard to test subcommands in isolation (most tests bypass `main()` entirely)

## Non-goals

- **No behavior changes.** `bench <cmd> --help` output must be byte-identical
  before and after every step. `--json` envelope shape and exit codes must
  not change.
- **No new features.** The `--out` flag (task #12) and approval gating
  (task #13) land separately so they don't confound this refactor's diff.
- **No type-checker tightening in this PR.** The mypy scope expansion
  happens in a follow-up; this refactor only reshuffles existing code.

## Safety net — land before any refactor starts

1. **Byte-identical `--help` snapshot test.** New test
   `benchmark/tests/unit/test_cli_help_snapshot.py`: for each subcommand,
   captures `bench <cmd> --help` output to a fixture under
   `benchmark/tests/fixtures/help_snapshots/`. Any drift fails the test.
2. **JSON envelope snapshot tests** for agent-critical commands
   (`bench --json runs --limit 3`, `bench get <fixture-run-id> --json`,
   `bench --json leaderboard status`). Use a fixture runs directory under
   `benchmark/tests/fixtures/sample_runs/`.
3. **Exit-code coverage**: assert `bench <cmd>` exits 0 on happy path, 1 on
   missing-arg, 2 on non-interactive refusal (once #13 lands).

If any of these fail mid-migration, revert the in-flight commit.

## Target layout

```
src/invisiblebench/cli/
├── __init__.py
├── runner.py            (dispatch + argparse wiring only, <500 LOC)
├── run_benchmark.py     (the run_benchmark() core + its helpers)
└── commands/
    ├── __init__.py
    ├── doctor.py        # ~60 LOC
    ├── runs.py          # ~120 LOC (+ --out from #12)
    ├── get.py           # ~70 LOC
    ├── leaderboard.py   # ~180 LOC (already partial in cli/leaderboard.py)
    ├── publish.py       # ~40 LOC (wires cli/publish.py)
    ├── stats.py
    ├── reliability.py
    ├── annotate.py
    ├── diff.py          # ~200 LOC
    ├── diagnose.py
    ├── audit.py
    ├── report.py
    ├── health.py
    ├── archive.py       # (wires cli/archive.py)
    ├── rescore.py       # (wires cli/rescore.py)
    └── README.md
```

Each command module exports two things:

```python
def register(subparsers: argparse._SubParsersAction) -> None:
    """Attach this subcommand's parser + arguments to the root."""

def run(args: argparse.Namespace) -> int:
    """Execute the command. Return exit code."""
```

`runner.py` becomes:

```python
def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_root_parser()
    subparsers = parser.add_subparsers(dest="command")

    for module in COMMAND_MODULES:
        module.register(subparsers)

    args = parser.parse_args(argv)
    if args.command is None:
        return run_benchmark(args)
    return _dispatch(args)
```

## Migration order (lowest blast radius first)

Run the full test suite + help-snapshot suite between every step. Commit
after every step. If a step reveals behavior coupling, stop and document.

### Step 1 — cold-path self-contained commands
- `doctor` (no shared state)
- `runs` (already isolated in `_run_runs`)
- `get` (already isolated in `_run_get`)
- `health` (small)
- `report` (small)

Expected LOC reduction in `runner.py`: ~350 LOC.

### Step 2 — diff + stats + reliability + annotate
Self-contained, but each has >100 LOC and its own helpers. Move the helpers
with the command.

Expected LOC reduction: ~900 LOC.

### Step 3 — rescore + diagnose + audit
Each wires an existing `cli/rescore.py`, `export/diagnostic.py`, or
`run_audit.py` module. Migration is mostly "move the argparse block + the
thin dispatch wrapper".

Expected LOC reduction: ~200 LOC.

### Step 4 — leaderboard + publish
Higher-risk — these are live-write commands. Once task #13 lands, they go
through the confirmation helper. Move after #13 is merged, not before.

Expected LOC reduction: ~400 LOC.

### Step 5 — archive + clean
These share args and dispatch to `cli/archive.py`. Small, do last to avoid
distraction.

Expected LOC reduction: ~80 LOC.

### Step 6 — extract `run_benchmark` core
The default command (no subcommand) is `run_benchmark()` at runner.py:1763,
966 LOC. Move the whole thing to `cli/run_benchmark.py` with its helpers.

Expected LOC reduction: ~1200 LOC.

After all steps, `runner.py` should be under 500 LOC: argparse root parser,
common options, and the dispatch loop.

## Verification after each step

```bash
uv run pytest benchmark/tests -q
uv run pytest benchmark/tests/unit/test_cli_help_snapshot.py -q
uv run ruff check .
uv run bench --help > /tmp/help.out && diff benchmark/tests/fixtures/help_snapshots/root.txt /tmp/help.out
uv run bench doctor
uv run bench --json runs --limit 3
```

All must pass before the step is committed.

## Rollback

Each step is a single commit. Rollback = `git revert <sha>`. No step should
span multiple commits; if scope grows mid-step, split the commit.

## Open questions

1. Does `run_benchmark` share enough state with subcommands to warrant
   putting dispatch inside it? (Guess: no — subcommands already return
   early before the default path.)
2. Should the `--json` envelope helper stay in `_agent_cli.py` or move into
   `commands/__init__.py`? (Guess: stays in `_agent_cli.py` — it's reused
   by `invisiblebench` binary too.)
3. Are there cross-command helpers (`_runs_dir`, `_load_run_metadata`,
   `_read_leaderboard_json`) that deserve their own `cli/common.py`?
   (Likely yes — those are used by at least `runs`, `get`, `leaderboard`,
   and `diff`.)
