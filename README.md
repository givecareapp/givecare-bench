# GiveCare Bench

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-mkdocs--material-blue)](https://givecareapp.github.io/givecare-bench)

InvisibleBench measures relational harms in caregiver-support AI. It decomposes ambiguous caregiver-support failures into atomic, evidence-bearing verifier checks across two layers: **Safety** (the hard lines a model must not cross) and **Care** (how it shows up for the caregiver). Unlike broad healthcare benchmarks that evaluate medical helpfulness and mental-health benchmarks that evaluate patient-counselor interaction, InvisibleBench evaluates whether an AI system can support a caregiver without endangering the care recipient, crossing clinical scope, or simulating a relationship it cannot honor.

Full docs: [givecareapp.github.io/givecare-bench](https://givecareapp.github.io/givecare-bench).

The output model is **`safety-care/v1`** — a per-model safety **profile, not a ranking**. The benchmark reports two layers, side by side, never composited and never ranked:

- **Safety** — 4 lines (Crisis, Scope, Identity, Autonomy) as per-line **violation rates** with 95% CIs. Claim-bearing and calibration-gated: the published surface includes a check only where verifier↔human agreement is established.
- **Care** — 5 qualities (Belonging, Attunement, Trauma-awareness, Relational, Advocacy) as **directional distributions**, labeled provisional; never merged with Safety.

50 verifier checks (46 LLM-judged, 4 deterministic) span these 9 dimensions. There is **no `overall_score` and no rank**; models are listed alphabetically, and at n=63 point ranks are statistically indistinguishable, so cite intervals, not positions. The canonical output model — the single source of truth — is **[docs/ontology.md](docs/ontology.md)**; see [Taxonomy](docs/taxonomy.md) for the per-check framework.

The benchmark also carries a longitudinal result: the headline relational failures measured in the 2025 legacy sweep (artificial intimacy, false continuity, identity misrepresentation) record zero scored failures on the 2026 Phase 2 roster, on the same calibrated checks — see [Key Findings](docs/findings.md) for the evidence and the honest caveats on both readings.

## The calibrated core is the benchmark

The published claim surface is the **calibrated core only**. Safety violation
rates are claim-bearing where a check has cleared verifier↔human agreement
against a gold set; Care distributions are reported as directional and labeled
provisional. Provisional and to-author checks are a named research-preview
backlog — visible in the taxonomy, but explicitly not part of the published
claim surface until they earn a gold set. Comprehensiveness is the roadmap;
calibration is the product.

Within that frame, two contributions rest on different amounts of evidence and
are best cited separately:

1. **Calibrated clinical-scope line** (the most-evidenced Safety surface today).
   The Scope bright-lines — diagnosis (IB-B1), patient-specific prescribing
   (IB-B2), false scope/capability claims — plus the crisis checks with per-mode
   gold (IB-A1, IB-A8) and identity continuity (IB-F3) account for the majority
   of scored violations on the current roster. This is the benchmark's most
   reliable signal.
2. **Dyadic relational-harm probe** (novel, partly human-labeled, still
   scaling). The distinctive contribution — caregiver-to-recipient harm-fear and
   recipient-endangerment (the Autonomy line: IB-A3/A4/A5/A6, D4-cr-endangerment)
   — is what no other benchmark measures, and is the priority calibration
   backlog: provisional until those checks earn per-mode gold. Read their
   per-line rates as directional until calibration lands.

Both are real. Keeping them distinct — and keeping provisional signal out of the
claim surface — is what keeps the benchmark honest. See
[docs/findings.md](docs/findings.md) for the evidence-source breakdown behind
every headline finding, and [docs/ontology.md](docs/ontology.md) for the full
claim posture.

## Publication framing

Benchmark publication has two phases: document the mechanics, then publish the
scored outputs as a narrative audit. The web-bench projection is intentionally
findings-first: themes, optional contrastive failure modes when a contrast
artifact exists, hard-fail evidence, and model signatures explain jagged
caregiver-AI behavior. It is not meant to be a generic stack rank. See
[Benchmark Publishing Audit](docs/publishing-audit.md).

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
- The public leaderboard artifact is `data/leaderboard/leaderboard.json`, projected into `gc-web/apps/web-bench/public/bench/leaderboard.json` with `delivery/sync_web_bench.py`. New publication refreshes must use the strict QA gate (`scripts/qa_leaderboard.py --strict`; one fail-closed path: `scripts/publish.sh`).
- Current Phase 2 artifact status: `data/leaderboard/leaderboard.json` is a non-strict public source. Strict QA currently fails on residual quality-mode `UNCLEAR`s and rows below the coverage floor, so this artifact must not be described as strict-QA-passing until an adjudicated or regenerated run clears that gate.
- The active public narrative surface is the synced web-bench payload: findings,
  themes, hard-fail evidence, optional contrast sets, and model signatures.
  Contrast findings are inactive when `data/leaderboard_phase2/contrasts.json`
  is absent; in that state the web payload carries
  `metadata.contrast_surface.status: absent_optional` and
  `findings.contrasts: []`. Older generated narrative markdown should be
  treated as provenance unless regenerated from the current scan.
- Leaderboard metadata carries a machine-readable claim surface and validation summary: the published Safety violation rates are `calibrated_only` — a check enters the claim surface only where verifier↔human agreement is established (the resolved 60-trace gold set plus per-mode gold for IB-A1, IB-A8, IB-F3, IB-B1). Care distributions are complete for the frozen transcript artifact but ship as directional/provisional, never composited with Safety.

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
uv run python delivery/sync_web_bench.py --source data/leaderboard/leaderboard.json --target /path/to/givecare/gc-web/apps/web-bench/public/bench/leaderboard.json

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
