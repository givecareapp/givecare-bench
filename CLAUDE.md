# GiveCare Bench

Operational map for InvisibleBench. Read `VISION.md` for measurement intent and
`AGENTS.md` for publication and safety rules.

## Map

| Path | Purpose |
| --- | --- |
| `checks/` | Check definitions, routing, prompts, calibration status |
| `benchmark/` | Public scenarios, inventory, configs, tests |
| `src/invisiblebench/cli/` | Run and inspect commands |
| `src/invisiblebench/evaluation/` | Registry, verifiers, aggregation, calibration |
| `src/invisiblebench/judge.py` | Scan planning and execution |
| `scripts/` | Scan, QA, publish, lint, and intake shims |
| `delivery/` | Public projections and web sync |
| `intake/` | Gitignored private candidate data |
| `internal/` | Local calibration and research material |
| `data/leaderboard/leaderboard.json` | Canonical public scorecard |

`docs/ontology.md` owns the public `safety-care/v1` model.
`docs/verifier-validation.md` owns current calibration evidence. Runtime versions
and inventory live in code/config, not this file.

Current contract snapshot (guarded against `benchmark/benchmark_inventory.json`):
checks: 50 across the registered taxonomy; public scenarios: `63`.

## Core commands

```bash
uv run bench doctor
uv run bench --full --dry-run
uv run bench --full -y --max-cost-usd <budget>
uv run bench runs --limit 25
uv run bench get <run-id>
uv run bench explain <model> <scenario> --failures
uv run bench review status
uv run bench review serve
```

Plan LLM scans before spending. Scan runs checkpoint rows and may resume only
when the original signature still matches.

## Scan and publication

```bash
uv run python scripts/run_scan.py --profile publish --dry-run --enable-llm <run>
uv run python scripts/run_scan.py --profile publish --enable-llm \
  --max-cost-usd "$SCAN_MAX_COST_USD" <run>
uv run bench review build --scan <scan>/per_run.jsonl \
  --out-dir internal/review/<batch>
uv run bench review status --dir internal/review/<batch>
uv run bench review serve --dir internal/review/<batch> --publication
uv run python scripts/review_ui/apply_scan_adjudications.py \
  --scan <scan>/per_run.jsonl --source-map internal/review/<batch>/source_map.json \
  --annotations internal/review/<batch>/review_annotations.jsonl
bash scripts/publish.sh <scan>/per_run.jsonl \
  ../gc-web/apps/web-bench/public/bench/leaderboard.json
```

`publish.sh` owns generate -> strict QA -> sync. The QA stamp proves exact
leaderboard bytes; direct sync without a fresh stamp must fail.

`delivery/combine_scans.py` accepts only provenance-complete scan plan v2
artifacts with one comparability fingerprint. Use
`scripts/resolve_unclear_scan.py` for bounded machine resolution; publication
escalations use the blind review export/apply pair above. Use
`scripts/rescore_diff.py` to prove refactors preserve verdicts.

## Review UI / ecosystem approval queue

`scripts/review_ui/app.py` is a self-contained Flask app with two jobs: the
blind gold-card reviewer flow (this repo's calibration evidence) and the
**ecosystem approval queue** (Hound plans, social veto window, wiki drafts)
at https://review.givecareapp.com. Contract, mechanisms, and truth rules:
`../.agents/approval-queue.md` (workspace level) — read it before touching
queue behavior.

- Runs as the `review-ui` systemd user unit on :3090
  (`systemctl --user restart review-ui`); Traefik route
  `~/traefik/dynamic/review.yml`.
- Tokens: `internal/review/tokens.txt` (gitignored, 600) —
  `token=<urlsafe> role=admin|reviewer id=<name>`; re-read per request.
- Expressions per gc-web `DESIGN.md`: reviewer pages editorial (external
  humans), admin pages console (`.dashboard` scope) — do not mix.
- Decisions land in the gates' native artifacts plus
  `../.agents/decisions.jsonl` (site-made wiki decisions also append
  `../gc-wiki/.review-queue/decisions.jsonl`).

Review links to the separately owned Workpad service at `/workpad/demo`.
Workpad source, scoped invitations, Markdown revisions, and provenance live
outside gc-bench at `/home/deploy/repos/workpad`; Flask/admin authority remains
separate.

## Candidate intake

```bash
uv run python scripts/intake/import_evals.py --evals-dir ../gc-evals/data --dry-run
uv run python scripts/intake/incident_registry.py intake/incidents.jsonl
bash scripts/intake/overnight-promote.sh --dry-run
```

The registry and candidate data stay under gitignored `intake/`; tracked code
contains only validators and import tooling. Candidate advancement requires
de-identification, privacy review, a contrast pair, a viable scorer route, and
recurrence or high consequence. The historical probe filename remains, but the
probe is manual and on demand. Results stay in `intake/review/` until human
promotion.

## Local gate

The pre-commit hook runs the required local checks. GitHub Actions are not the
private proof gate. Public docs deploy separately with
`scripts/deploy-docs.sh`. `AGENTS.md` owns the exact proof commands.

Contributor entry points: `docs/quickstart.md`, `docs/architecture.md`,
`docs/scoring-rubric.md`, `docs/verifier-validation.md`, and `DESIGN.md` for the
target internal decomposition.
