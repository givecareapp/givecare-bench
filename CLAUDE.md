# GiveCare Bench

Operational map for InvisibleBench. Read `VISION.md` for intent and
`AGENTS.md` for guardrails.

## Map

| Path | Purpose |
| --- | --- |
| `checks/` | Check definitions, criteria, evidence, and severity |
| `benchmark/` | Public scenarios, inventory, contract, and tests |
| `src/invisiblebench/cli/` | Transcript, scan, inspect, and run commands |
| `src/invisiblebench/models/scan.py` | Typed scan and judgment contract |
| `src/invisiblebench/jury_card.py` | Standard Jury Card from saved evidence |
| `src/invisiblebench/evaluation/` | Check registry and single model judgment |
| `src/invisiblebench/scoring.py` | Deterministic Safety/Care projection and QA |
| `src/invisiblebench/judge.py` | Scan planning and execution |
| `scripts/` | Scan, QA, inventory, intake, and Evidence drivers |
| `delivery/watch/` | Dated release-watch proposals |
| `intake/` | Gitignored private candidate data |
| `results/<UTC-run-id>/` | One private run: Jury Card and its evidence bundle |
| `results/archive/` | Historical runs and retired reports |
| `data/leaderboard/leaderboard.json` | Committed owner projection |

`src/invisiblebench/models/scan.py` defines the scan contract.
`src/invisiblebench/scoring.py` derives the `safety-care/v3` public projection.
`docs/methodology.md` explains the rates. Runtime versions and inventory live
in code and machine-readable configuration.

## Core commands

```bash
uv run bench doctor
uv run bench --full --dry-run
uv run bench --full -y --max-cost-usd <budget>
uv run bench runs --limit 25
uv run bench get <run-id>
uv run bench jury <run-id>
uv run bench explain <model> <scenario> --failures
```

Plan every paid scan first:

```bash
uv run python scripts/run_scan.py plan <run> --llm-model <judge>
uv run python scripts/run_scan.py run \
  --plan <run>/scan_plan.json --max-cost-usd <budget>
```

Run directories use UTC `YYYY-MM-DD_HH-MM-SSZ`. Model identity stays in the manifest
and Jury Card. A later run of the same model gets a new directory. The CLI
rejects overwrites and ambiguous run prefixes.

Planning freezes a single source run in place. To judge saved responses again,
use `--output <new-run-directory>`. That creates a separate portable snapshot.
Repeat the run command to resume. Saved judgments and costs remain intact.
Completion writes `jury-card.md`; `bench jury` regenerates it without API calls.
The card replaces separate per-run reports and scorecard exports. Its marked
commentary section stays outside the ledger and survives regeneration against
the same evidence. Public projection candidates remain separate release inputs.

## Scan and projection

The active path has one LLM judge per active check. Each conversation and
check has one completed judgment. Results use `PASS`, `FAIL`, `UNCLEAR`, or
`NOT_APPLICABLE`. A critique can refer to a saved decision. It stays outside
the ledger and cannot change a verdict or block publication.

The Evidence driver keeps two operations:

```bash
helm evidence plan --driver evidence-driver.json --operation corpus.apply \
  --input /tmp/gc-bench-candidates.json --as-of YYYY-MM-DD \
  --output /tmp/gc-bench-candidate-plan.json
helm evidence plan --driver evidence-driver.json --operation corpus.project \
  --input /tmp/gc-bench-leaderboard-input.json --as-of YYYY-MM-DD \
  --output /tmp/gc-bench-leaderboard-plan.json
```

`corpus.apply` is a human content-promotion gate. It does not approve model
verdicts. `corpus.project` is deterministic and writes the committed owner
projection from hash-bound inputs. Private conversations, judge decisions,
scenario text, expected answers, and prompts stay in protected paths.

## Candidate intake

```bash
uv run python scripts/intake/import_evals.py \
  --selected-id <eval-record-id> \
  --output /tmp/gc-bench-candidates.json
helm evidence plan --driver evidence-driver.json --operation corpus.apply \
  --input /tmp/gc-bench-candidates.json --as-of YYYY-MM-DD \
  --output /tmp/gc-bench-candidate-plan.json
uv run python scripts/intake/incident_registry.py intake/incidents.jsonl
```

Candidate data stays under gitignored `intake/`. Review the resulting Git diff
before committing promoted scenario content.

## Local proof

```bash
uv run ruff check .
uv run pytest benchmark/tests -q
uv run python scripts/lint_turn_indices.py --strict
helm evidence driver check --driver evidence-driver.json
```

Public docs deploy separately with `scripts/deploy-docs.sh`.
