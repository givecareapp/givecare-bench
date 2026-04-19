# Install

> **Diátaxis: how-to** — install `bench` and `invisiblebench` so they're
> invokable from any folder.

## TL;DR

```bash
cd /path/to/givecare-bench
uv sync --extra dev
uv tool install --from . invisiblebench
command -v bench    # should print a path under ~/.local/share/uv/tools
```

After `uv tool install`, `bench` and `invisiblebench` are on PATH and agents
or scripts in any working directory can invoke them.

## Install options

### Option 1 — in-project (fastest, cwd-coupled)

```bash
cd /path/to/givecare-bench
uv sync --extra dev
uv run bench --help
```

`uv run bench` resolves via the project's `.venv`. Works only from inside the
repo or via `uv run --project /path/to/givecare-bench bench …` from outside.

### Option 2 — tool install (recommended for agents)

```bash
uv tool install --from /path/to/givecare-bench invisiblebench
```

This installs the `bench` and `invisiblebench` entrypoints into
`~/.local/share/uv/tools/invisiblebench/bin/` and symlinks them onto
`$PATH`. After this, any shell can do:

```bash
bench doctor
bench --json runs --limit 10
```

Re-run `uv tool install --from /path/to/givecare-bench invisiblebench --reinstall`
after pulling changes to pick up the new code.

### Option 3 — absolute venv path (ad-hoc, no install)

```bash
/path/to/givecare-bench/.venv/bin/bench --help
```

Works without any install step as long as `uv sync` has been run in the
project. Useful for one-off scripts and CI. Avoid in agent workflows — hard
to remember and brittle to path changes.

## Auth + env

`bench doctor` checks for the runtime auth it needs:

```
[PASS] LLM API key (OPENROUTER_API_KEY | OPENAI_API_KEY | ANTHROPIC_API_KEY)
[PASS] runs_dir exists (/path/to/repo/results)
[PASS] runs_dir writable
```

Copy `.env.example` to `.env` in the repo root and fill in at least one LLM
provider key.

## Cross-folder verification checklist

Used by the companion `bench` skill to confirm a new install:

```bash
cd /tmp
command -v bench                          # 1. on PATH
bench --help | head                       # 2. help prints
bench doctor                              # 3. auth/env precheck
bench --json runs --limit 3               # 4. discovery read
bench get <run-id-from-step-4> --json     # 5. exact read by id
```

`runs_dir` is resolved relative to the installed package, not the caller's
cwd, so discovery and reads are cwd-independent.

## Uninstall

```bash
uv tool uninstall invisiblebench
```
