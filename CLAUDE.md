# GiveCare Bench

Operational map for InvisibleBench. Read `VISION.md` for intent and
`AGENTS.md` for guardrails.

## Map

| Path | Purpose |
| --- | --- |
| `checks/` | Check definitions, criteria, evidence, and severity |
| `benchmark/` | Public scenarios, inventory, contract, and tests |
| `src/invisiblebench/cli/` | Transcript, scan, inspect, and run commands |
| `src/invisiblebench/evaluation/` | Registry, mode engine, and LLM verifier |
| `src/invisiblebench/judge.py` | Scan planning and execution |
| `scripts/` | Scan, QA, inventory, intake, and Evidence drivers |
| `delivery/` | Current owner-projection helpers and watch output |
| `intake/` | Gitignored private candidate data |
| `results/` | Gitignored raw transcripts and scan artifacts |
| `data/leaderboard/leaderboard.json` | Committed owner projection |

The public output model is `safety-care/v2` in `docs/methodology.md` and
`benchmark/configs/scoring.yaml`. Runtime versions and inventory live in code
and machine-readable configuration.

## Core commands

```bash
uv run bench doctor
uv run bench --full --dry-run
uv run bench --full -y --max-cost-usd <budget>
uv run bench runs --limit 25
uv run bench get <run-id>
uv run bench explain <model> <scenario> --failures
```

Plan every paid scan first:

```bash
uv run python scripts/run_scan.py <run> \
  --dry-run --llm-model <judge>
uv run python scripts/run_scan.py <run> \
  --plan <scan>/scan_plan.json \
  --max-cost-usd <budget> --llm-model <judge>
```

The live command requires the dry-run plan, matching source, matching judge,
and explicit cost ceiling. Checkpoints resume only when their source and judge
signature still match.

## Scan and projection

The active path has one LLM judge per active check. Each scan writes one mode
result per active check and uses explicit `NOT_APPLICABLE` rows for suppressed
checks. Results use `PASS`, `FAIL`, `UNCLEAR`, or `NOT_APPLICABLE`. Optional
critique is metadata only.

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
