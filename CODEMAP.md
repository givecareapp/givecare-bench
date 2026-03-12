# Codemap

Diátaxis: reference

Generated: 2026-03-12

## Architecture

InvisibleBench is a Python benchmark package for multi-turn caregiving AI evaluation. One benchmark core handles scenario loading, transcript scoring, artifact writing, and run audits; harnesses decide how transcripts are generated. The implemented targets are `llm/raw`, `givecare/live`, and `givecare/orchestrator`.

## Directory Structure

| Path | Purpose | Key Files |
|------|---------|-----------|
| `benchmark/invisiblebench/cli/` | CLI entry points and subcommands | `runner.py`, `leaderboard.py`, `publish.py` |
| `benchmark/invisiblebench/evaluation/` | Scoring pipeline and dimension scorers | `orchestrator.py`, `scorers/` |
| `benchmark/invisiblebench/export/` | Human-readable outputs | `reports.py`, `diagnostic.py` |
| `benchmark/invisiblebench/models/` | Scenario + model config schemas | `config.py`, `scenario.py`, `results.py` |
| `benchmark/invisiblebench/` | Harness plumbing and run artifacts | `harnesses.py`, `givecare_orchestrator.py`, `results_io.py`, `run_artifacts.py`, `run_audit.py`, `failure_taxonomy.py` |
| `benchmark/scenarios/` | Benchmark corpus by MECE category | `safety/`, `empathy/`, `context/`, `continuity/`, `confidential/` |
| `benchmark/scripts/` | Live/provider integrations and validation helpers | `givecare_provider.py`, `validation/`, `leaderboard/generate_leaderboard.py` |
| `benchmark/adapters/givecare-orchestrator/` | TypeScript bridge for direct Pi orchestrator evals | `src/bridge.ts`, `build.mjs` |
| `benchmark/tests/` | Unit and contract tests | `unit/test_harnesses.py`, `unit/test_run_audit.py`, `unit/test_givecare_orchestrator_bridge.py` |
| `docs/` | Public docs site | `index.md`, `architecture.md`, `methodology.md` |
| `data/v2/` | Published leaderboard artifacts | `leaderboard.json` |
| `results/` | Gitignored run outputs | `run_*`, `givecare/run_*`, `givecare_orchestrator/run_*`, `leaderboard_ready/` |

## Entry Points

| Entry | File | Description |
|------|------|-------------|
| Main CLI | `benchmark/invisiblebench/cli/runner.py` | `bench` command: raw eval, GiveCare harnesses, audit, stats, diagnostics |
| YAML scorer CLI | `benchmark/invisiblebench/yaml_cli.py` | Score a transcript/scenario pair directly |
| Live GiveCare harness | `benchmark/scripts/givecare_provider.py` | Generates transcripts through the real product path |
| Orchestrator harness | `benchmark/invisiblebench/givecare_orchestrator.py` | Builds/invokes the TS bridge and runs scenarios turn-by-turn |
| Orchestrator bridge | `benchmark/adapters/givecare-orchestrator/src/bridge.ts` | Invokes `@givecare/pi-orchestrator` with benchmark-owned runtime fixtures |
| Leaderboard generator | `benchmark/scripts/leaderboard/generate_leaderboard.py` | Builds the published leaderboard from canonical result docs |

## Data Flow

1. CLI resolves a harness/mode pair in `harnesses.py`.
2. Scenario files are selected from `benchmark/scenarios/`.
3. A transcript generator runs:
   - raw LLM path in `runner.py`
   - live GiveCare path in `givecare_provider.py`
   - direct orchestrator path in `givecare_orchestrator.py` + `src/bridge.ts`
4. `evaluation/orchestrator.py` scores transcripts with shared gates + quality dimensions.
5. `results_io.py` writes primary per-model artifacts to `model_results/*.json` and compatibility aggregates.
6. `run_audit.py` classifies run failure modes and decides whether the run is publishable.
7. Leaderboard/publish commands load those artifacts via `run_artifacts.py` and respect existing audits.

## Key Patterns

- **Harness/mode split**: `harness` chooses the target family; `mode` chooses how that target runs.
- **Primary artifact = per-model JSON**: `model_results/*.json` is canonical; `all_results.json` is compatibility output.
- **Audit-first promotion**: runs are written first, then audited, then optionally promoted to leaderboard/publish flows.
- **Branching transcripts**: `resolve_branch()` adapts user turns deterministically without changing scorer contracts.
- **Benchmark-owned orchestrator runtime**: the direct GiveCare harness avoids editing `give-care-mono` by using a local TS bridge and runtime shim.

## Dependencies (non-obvious)

| Package / Tool | Why |
|----------------|-----|
| `pydantic` | Scenario/result contracts |
| `rich` | CLI tables, progress, and interactive output |
| `jsonlines` | Transcript IO helpers |
| `python-dotenv` | Local API-key loading for CLI runs |
| Node 22 + `esbuild` from `give-care-mono` | Bundles the direct orchestrator bridge without changing the mono repo |

## Common Tasks

| Task | Steps |
|------|-------|
| Run raw benchmark | `uv run bench --full -y` or `uv run bench -m <model> -y` |
| Run GiveCare live harness | `uv run bench --harness givecare --mode live -y` |
| Run direct orchestrator harness | `uv run bench --harness givecare --mode orchestrator -y` |
| Audit a run | `uv run bench audit results/<run_dir>/` |
| Add results to leaderboard | Run benchmark, confirm `run_audit.json` is publishable, then use `bench leaderboard add <run_dir>` |
| Add a new harness target | Extend `harnesses.py`, implement transcript generation, reuse shared scoring + artifact writers |
| Add a new scenario | Create JSON under the correct category in `benchmark/scenarios/`, then run validation + tests |
