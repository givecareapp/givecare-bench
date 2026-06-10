# GiveCare Bench

[![CI](https://github.com/givecareapp/givecare-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/givecareapp/givecare-bench/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-mkdocs--material-blue)](https://givecareapp.github.io/givecare-bench)

InvisibleBench is a calibrated deployment gate for relational harms in caregiver-support AI. It decomposes ambiguous caregiver-support failures into atomic, evidence-bearing verifier checks across safety, compliance, communication, coordination, and boundary integrity. Unlike broad healthcare benchmarks that evaluate medical helpfulness and mental-health benchmarks that evaluate patient-counselor interaction, InvisibleBench evaluates whether an AI system can support a caregiver without endangering the care recipient, crossing clinical scope, or simulating a relationship it cannot honor.

Full docs: [givecareapp.github.io/givecare-bench](https://givecareapp.github.io/givecare-bench).

The benchmark uses a gate-then-quality architecture. Safety (A) and compliance (B) are fail-closed gates -- any failure zeroes the score. Three quality dimensions -- communication (C), coordination (D), and boundary integrity (F) -- measure how the model speaks, what it does next, and how honestly it represents itself. 53 verifier checks across these 5 dimensions are calibrated against human expert labels. See [Taxonomy](docs/taxonomy.md) for the full framework.

The primary output is a **failure-mode profile**: which checks each model fails, at what rate, with quoted transcript evidence. Hard-fail rates and failure signatures are the strongest public claims; overall score is a convenience summary, not the headline metric. The quality-layer judges (communication, coordination, boundary dimensions) have not yet cleared validation-grade agreement with human labels — treat `overall_score`, dimension scores, and rank as navigation aids until they do; the same caveat ships inside the leaderboard artifact's metadata.

The benchmark also carries a longitudinal result: the headline relational failures measured in the 2025 legacy sweep (artificial intimacy, false continuity, identity misrepresentation) record zero scored failures on the 2026 Phase 2 roster, on the same calibrated checks — see [Key Findings](docs/findings.md) for the evidence and the honest caveats on both readings.

## Two distinct claims

InvisibleBench makes two claims that rest on different amounts of evidence. They
are best cited separately rather than blended into a single leaderboard number:

1. **Calibrated clinical-scope gate** (validated, statistically robust). The
   compliance bright-lines — diagnosis (IB-B1), patient-specific prescribing
   (IB-B2), false scope/capability claims, identity disclosure — are evaluated
   on every scenario, validated on the resolved 60-trace gold set, and account
   for the majority of hard failures on the current leaderboard. This is the
   benchmark's most reliable signal today.
2. **Dyadic relational-harm probe** (novel, partly human-labeled, still
   scaling). The distinctive contribution — caregiver-to-recipient harm-fear
   (IB-A3), recipient aggression (IB-A3b), crisis-signal negation (IB-A8),
   artificial intimacy and false continuity (F) — is what no other benchmark
   measures. Some of these checks (notably IB-A3) currently fire on only one or
   two scored scenarios; their strongest evidence lives in the human-card
   answer key, not yet the scored corpus. Densifying these scenarios is active
   work. Read per-check safety rates as directional until eligibility grows.

The benchmark is marketed on claim 2 but, in raw published numbers, currently
measures claim 1 most. Both are real. Keeping them distinct is what keeps the
benchmark honest. See [docs/findings.md](docs/findings.md) for the
evidence-source breakdown behind every headline finding.

## Publication framing

Benchmark publication has two phases: document the mechanics, then publish the
scored outputs as a narrative audit. The web-bench projection is intentionally
findings-first: themes, contrastive failure modes, hard-fail evidence, and
model signatures explain jagged caregiver-AI behavior. It is not meant to be a
generic stack rank. See [Benchmark Publishing Audit](docs/publishing-audit.md).

## Public, internal, and historical

### Public
These are the parts external users should rely on:
- `checks/`: the taxonomy — one YAML per check (definition, routing, judge prompt)
- `benchmark/`: public scenario corpus, scoring contract, tests
- `src/invisiblebench/`: runtime package, scoring, CLI, adapters
- `scripts/`: benchmark pipeline (run scan, leaderboard, QA, publish, rescore gate)
- `delivery/`: projections to consumers (web-bench sync, contrast analysis, taxonomy snapshot)
- `docs/`: public docs
- `data/leaderboard/`: generated public leaderboard artifact

### Internal-active
These are versioned in the repo, but they are not part of the public benchmark contract:
- `internal/autoresearch/`: scenario optimization campaigns and spread analysis
- `internal/evals/`: judge analysis, labeling, and scorer validation work
- `internal/papers/`: paper source and research artifacts

### Historical
These are retained for provenance, not day-to-day use:
- `archive/benchmark/`
- `archive/docs/`
- `archive/internal/`
- `archive/scenarios/`
- `archive/scripts/`

## Active repo shape

```text
givecare-bench/
├── checks/               # the taxonomy: one flat YAML per check
├── benchmark/            # public scenario corpus, scoring contract, tests
├── src/invisiblebench/   # runtime package (run / judge / publish / calibrate)
├── scripts/              # benchmark pipeline utilities
├── delivery/             # projections to consumers (web sync, snapshots)
├── docs/                 # public documentation
├── data/leaderboard/     # generated public artifacts
└── archive/              # historical material only
```

(Local working trees also carry gitignored operator directories — intake/,
internal/, results/ — that are not part of the public contract.)

## Public release policy

- Public leaderboard scope is benchmark-core only.
- Publicly comparable runs use the raw `llm` surface.
- GiveCare/Mira V2 product runs use `--harness givecare --mode v2` and are not part of the public comparative leaderboard.
- Private confidential scenarios are loaded externally and are not stored in this repo.
- Every scenario file embeds a contamination canary GUID (`benchmark/scenarios/CANARY.txt`). Trainers should filter on it; a model that can reproduce the GUID has trained on benchmark data.
- The public leaderboard artifact is `data/leaderboard/leaderboard.json`, projected into `gc-web/apps/web-bench/public/bench/leaderboard.json` with `delivery/sync_web_bench.py` and QA-gated with `scripts/qa_leaderboard.py --strict` (one fail-closed path: `scripts/publish.sh`).
- The active public narrative surface is the synced web-bench payload: findings,
  themes, contrast sets, and model signatures. Older generated narrative
  markdown should be treated as provenance unless regenerated from the current
  scan.
- Leaderboard metadata carries a machine-readable claim surface and validation summary: the public hard-fail layer (`safety`, `compliance`, public hard-fail rate) is calibrated on the resolved 60-trace gold set; quality-mode verdicts are complete for the frozen transcript artifact but should still be described more cautiously than public gates.

## Quickstart

Run the benchmark against **your own model** (any OpenRouter id) in an
afternoon: [docs/quickstart.md](docs/quickstart.md). The short version:

```bash
uv sync --extra dev && export OPENROUTER_API_KEY=...
uv run bench -m "your-org/your-model" -y                                  # run
uv run python scripts/run_scan.py --profile dev --enable-llm results/run_<id>   # judge (core profile)
uv run bench explain "your-model" <scenario> --failures --scan <scan>/per_run.jsonl  # evidence
```

## Core commands

```bash
uv run pytest benchmark/tests -q
uv run ruff check .
uv run bench --help
uv run bench doctor                                 # validate env vars + runs dir
uv run bench --full --dry-run
uv run bench --full --scenario-parallel 8 -y
uv run bench runs --limit 25 --offset 0             # list runs (paged)
uv run bench get <run-id>                           # read a single run's metadata
uv run bench --json runs                            # JSON envelope for agents
uv run bench --json runs --out /tmp/runs.json       # write full payload to file; stdout = summary envelope
uv run python scripts/lint_turn_indices.py --strict
uv run python scripts/run_scan.py results/run_... --profile dev --dry-run --enable-llm
uv run python scripts/run_scan.py results/run_... --profile publish --enable-llm
uv run python scripts/generate_leaderboard.py --input <scan>/per_run.jsonl --output data/leaderboard
uv run python scripts/qa_leaderboard.py --scan <scan>/per_run.jsonl --leaderboard data/leaderboard/leaderboard.json --manual-adjudications <scan>/manual_adjudications.json --strict
uv run python scripts/sync_web_bench_leaderboard.py --source data/leaderboard/leaderboard.json --target /path/to/givecare/gc-web/apps/web-bench/public/bench/leaderboard.json

# Or run generate -> strict QA -> sync as one fail-closed command.
# Aborts before writing the web target if the QA gate fails:
./scripts/publish.sh <scan>/per_run.jsonl /path/to/gc-web/apps/web-bench/public/bench/leaderboard.json
```

Both `bench` and `invisiblebench` follow the agent-friendly CLI standard:
`NO_COLOR=1` is respected, `bench --json` / `--format json` wraps `runs`,
`stats`, and `leaderboard` output in a `{status, command, data}` envelope, and
`invisiblebench --doctor` plus `invisiblebench --list-runs --limit N --offset M`
mirror the paged run index. `--out PATH` (on `runs`, `get`, and `leaderboard
status`) writes the full payload to disk and emits a
`{path, byte_count, record_count}` summary. Live writes (`leaderboard
add/rebuild`, `archive`) refuse in non-interactive shells unless `--yes` is
passed.

## Contributing and reporting

- [CONTRIBUTING.md](CONTRIBUTING.md) — dev setup, scenario contract, PR checklist
- [SECURITY.md](SECURITY.md) — private security-advisory channel
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — Contributor Covenant v2.1
- Bugs and feature requests: [GitHub Issues](https://github.com/givecareapp/givecare-bench/issues)
