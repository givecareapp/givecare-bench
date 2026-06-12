# Clawpatch Benchmark Watchlist

Use Clawpatch as a review ledger for benchmark integrity, not as an automatic
fixer. The goal is to catch scenario-contract drift, verifier/calibration
mistakes, fail-closed publication gaps, and leaderboard projection errors that
normal tests may not explain in claim terms.

## Operating Rules

- Keep `.clawpatch/` local. Do not commit generated maps, findings, reports, or
  patch attempts.
- Review first. Do not run `clawpatch fix` until a human has triaged the
  finding and picked a scope.
- Keep private intake, run outputs, confidential holdouts, and provider secrets
  out of Clawpatch state unless explicitly reviewed.
- Do not use findings to publish claims from uncalibrated verifier behavior.

## Setup

```bash
clawpatch --version
clawpatch init
clawpatch map --source agent --reasoning-effort low
```

## Canonical Watchlist

| Watch item | Trigger it when changes touch | Ask Clawpatch to look for | Local verification anchors |
| --- | --- | --- | --- |
| Scenario contract | `benchmark/scenarios`, `benchmark/configs`, scenario models/loaders | Legacy tier fields, invalid categories, turn-index drift, contamination canary loss, public/private data leakage. | `uv run pytest benchmark/tests -q`, `uv run python scripts/lint_turn_indices.py --strict`. |
| Check taxonomy | `checks/*.yaml`, check registry, routing | Missing calibration block, wrong scope/eligible modes, prompt-template drift, hard-fail claim unsupported. | Calibration gate tests, `uv run pytest benchmark/tests -q`. |
| Verifiers and fail-closed behavior | `src/invisiblebench/evaluation/**`, `judge.py`, scoring contract | UNCLEAR/FAIL semantics mixed, retry exhaustion not fail-closed, evidence-free public fail, coverage floor bypass. | `uv run pytest benchmark/tests/unit/test_fail_closed_boundaries.py benchmark/tests/unit/test_calibration_gate.py`. |
| Run/scan pipeline | `src/invisiblebench/cli`, `scripts/run_scan.py`, result IO | Non-comparable rows, stale version constants, brittle JSONL IO, unsafe defaults for live writes. | `uv run bench doctor`, `uv run pytest benchmark/tests -q`. |
| Publish path | `scripts/generate_leaderboard.py`, `scripts/qa_leaderboard.py`, `src/invisiblebench/publish.py`, `delivery/sync_web_bench.py` | Hand-edited leaderboard, QA bypass, web-bench sync before strict gate, stale narrative fields. | `bash scripts/publish.sh <scan> <target>` in reviewed context; publish verb tests. |
| Calibration evidence | Public calibration docs and tests | Human gold provenance lost, scorer-vs-gold audit not updated, private internal artifacts leaking public claims. Internal folders are excluded by default; review them only with an explicit owner-approved temporary scope. | Public calibration docs and tests. |
| GiveCare harness | V2 HTTP harness, `bench --harness givecare` paths | Product-specific policy baked into benchmark runtime, leaked private traces, env-key ambiguity. | `uv run bench --harness givecare --mode v2 -y` only when env is intentionally set. |

## Triage

Treat findings as review input. A finding is actionable only after the claim
surface, evidence path, and regression gate are clear.
