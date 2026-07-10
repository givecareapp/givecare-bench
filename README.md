# GiveCare Bench

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-mkdocs--material-blue)](https://givecareapp.github.io/givecare-bench)

InvisibleBench measures relational harms in caregiver-support AI. It decomposes ambiguous caregiver-support failures into atomic, evidence-bearing verifier checks across two layers: **Safety** (the hard lines a model must not cross) and **Care** (how it shows up for the caregiver). Unlike broad healthcare benchmarks that evaluate medical helpfulness and mental-health benchmarks that evaluate patient-counselor interaction, InvisibleBench evaluates whether an AI system can support a caregiver without endangering the care recipient, crossing clinical scope, or simulating a relationship it cannot honor.

Full docs: [givecareapp.github.io/givecare-bench](https://givecareapp.github.io/givecare-bench).

The output model is **`safety-care/v1`** — a per-model safety **profile, not a ranking**. The benchmark reports two layers, side by side, never composited and never ranked:

- **Safety** — 4 lines (Crisis, Scope, Identity, Autonomy) as per-line **violation rates** with 95% CIs. Claim-bearing only for `claim_ready` checks; the current published claim surface is empty.
- **Care** — 5 qualities (Belonging, Attunement, Trauma-awareness, Relational, Advocacy) as **directional distributions**, labeled `not_claim_ready`; never merged with Safety.

50 verifier checks (46 LLM-judged, 4 deterministic) span these 9 dimensions. There is **no `overall_score` and no rank**; models are listed alphabetically, and at n=63 point ranks are statistically indistinguishable, so cite intervals, not positions. The canonical output model — the single source of truth — is **[docs/ontology.md](docs/ontology.md)**; see [Taxonomy](docs/taxonomy.md) for the per-check framework.

No result artifact is checked in until it passes the current contract's strict
QA gate. The live `--full` command targets 15 OpenRouter models × 63 public
scenarios. The 2026-07-10 live-calibrated budget is about **$49.71 for
transcript generation**, then **$171 base / $456 conservative** for the
publication judge scan across all 15 models. Budget roughly **$221–$506 end to
end**, not the transcript number alone.

## The calibrated core is the benchmark

The published claim surface is the **calibrated core only**, gated on a binary
claim model: a check publishes a Safety claim only when it is **`claim_ready`** —
its verifier has cleared verifier↔human agreement against an independent,
human-labeled, natural-case calibration set. **As of 2026-07-01, 0 of 50 checks
are `claim_ready`, so the published claim surface is empty.** The 19 hard-fail
checks carry disclosed development evidence (an authored AI-panel unit test on
synthetic cards — not validation) but make no public claim; Care
distributions remain directional. Everything not `claim_ready` is a visible
research-preview backlog. Comprehensiveness is the roadmap; calibration is the
product.

Within that frame, two contributions rest on different amounts of evidence and
are best cited separately:

1. **Clinical-scope development signal** (the most-evidenced Safety surface today).
   The Scope bright-lines — diagnosis (scope.diagnosis), patient-specific prescribing
   (scope.prescribing), false scope/capability claims — plus the crisis checks with per-mode
   gold (crisis.passive-ideation, crisis.false-reassurance) and identity
   continuity (identity.memory-claim) form the benchmark's strongest
   development-evidence group, but remain `not_claim_ready`.
2. **Dyadic relational-harm probe** (novel, partly human-labeled, still
   scaling). The distinctive contribution — caregiver-to-recipient harm-fear and
   recipient-endangerment (crisis.harm-intent, crisis.abuse-neglect,
   crisis.acute-medical, crisis.exploitation, autonomy.override)
   — is the benchmark's distinguishing probe and priority calibration
   backlog: `not_claim_ready` until those checks earn independent human
   calibration. Read their
   per-line rates as directional until calibration lands.

Keeping these evidence levels distinct—and keeping `not_claim_ready` signal out
of the claim surface—is what keeps the benchmark honest. See
[docs/verifier-validation.md](docs/verifier-validation.md) for the evidence
ledger and [docs/ontology.md](docs/ontology.md) for the full claim posture.

## Publication framing

Benchmark publication has two phases: document the mechanics, then publish the
scored outputs. The published artifact is the **lean `safety-care/v1`**
payload — `{schema, notes, scan_metadata, models}`, where each model entry
carries `safety` (per-line violation rates, aggregate, severity breakdown,
`calibrated_only`) and `care` (per-quality distributions), never composited or
ranked. There is no `findings` block: thematic failure clusters, contrastive
pairs, and per-model signatures are **not** in the lean payload today — they
are deferred to a re-authored Safety/Care artifact-v2. See
[Benchmark Publishing Audit](docs/publishing-audit.md) for the two-phase
publication model and what a v2 findings layer would add.

## Public and internal surfaces

### Public
These are the parts external users should rely on:
- `checks/`: the taxonomy — one YAML per check (definition, routing, judge prompt)
- `benchmark/`: public scenario corpus, scoring contract, tests
- `src/invisiblebench/`: runtime package, scoring, CLI, adapters
- `scripts/`: benchmark pipeline (run scan, leaderboard, QA, publish, rescore gate)
- `delivery/`: projections to consumers (web-bench sync, contrast analysis, taxonomy snapshot)
- `docs/`: public docs
- `data/leaderboard/`: generated only by the fail-closed publication path

### Internal-active
These are versioned in the repo, but they are not part of the public benchmark contract:
- `internal/autoresearch/`: scenario optimization campaigns and spread analysis
- `internal/evals/`: judge analysis, labeling, and scorer validation work
- `internal/papers/`: paper source and research artifacts

## Active repo shape

```text
givecare-bench/
├── checks/               # the taxonomy: one YAML per check under layer/dimension dirs
├── benchmark/            # public scenario corpus, scoring contract, tests
├── src/invisiblebench/   # runtime package (run / judge / publish / calibrate)
├── scripts/              # benchmark pipeline utilities
├── delivery/             # projections to consumers (web sync, snapshots)
├── docs/                 # public documentation
└── data/leaderboard/     # created only after strict QA passes
```

(Local working trees also carry gitignored operator directories — intake/,
internal/, results/ — that are not part of the public contract.)

## Public release policy

- Public leaderboard scope is benchmark-core only.
- Publicly comparable runs use the raw `llm` surface.
- GiveCare/Mira V2 product runs use `--harness givecare --mode v2` and are not part of the public comparative leaderboard.
- Private confidential scenarios are loaded externally and are not stored in this repo.
- Every scenario file embeds a contamination canary GUID (`benchmark/scenarios/CANARY.txt`). Trainers should filter on it; a model that can reproduce the GUID has trained on benchmark data.
- The public leaderboard artifact is `data/leaderboard/leaderboard.json`, projected into `gc-web/apps/web-bench/public/bench/leaderboard.json` with `delivery/sync_web_bench.py`. New publication refreshes must use the strict QA gate (`scripts/qa_leaderboard.py --strict`; one fail-closed path: `scripts/publish.sh <scan>/per_run.jsonl <web-target>`).
- `bench health` reports the absence or drift of generated local projections;
  it does not publish, sync, or write.
- There is no checked-in result artifact. A fresh run must complete transcript
  generation, current-contract scanning, artifact generation, and strict QA
  before publication.
- The active public surface is the lean `safety-care/v1` web-bench payload:
  `schema`, `notes`, `scan_metadata`, and `models` (each carrying `safety` and
  `care`). There is no `findings` block in the current payload — themes,
  contrast sets, and per-model signatures are deferred to a re-authored
  Safety/Care artifact-v2 (see [docs/publishing-audit.md](docs/publishing-audit.md)).
- Leaderboard metadata carries a machine-readable claim surface and validation summary: the published Safety violation rates are `calibrated_only` — a check enters the claim surface only when it is `claim_ready`. Today that surface is empty (0 of 50 checks). Care distributions ship as directional/`not_claim_ready`, never composited with Safety.

## Quickstart

Run the benchmark against **your own model** (any OpenRouter id) in an
afternoon: [docs/quickstart.md](docs/quickstart.md). The short version:

```bash
uv sync --extra dev && export OPENROUTER_API_KEY=...
uv run bench -m "your-org/your-model" --dry-run                            # plan transcript budget
uv run bench -m "your-org/your-model" -y --max-cost-usd 25                 # generate transcripts
uv run python scripts/run_scan.py --profile dev --enable-llm --max-cost-usd 25 --llm-model openai/gpt-5-mini results/run_<id>   # judge (core profile)
uv run bench explain "your-model" <scenario> --failures --scan <scan>/per_run.jsonl  # scan evidence; raw/internal score fields
```

## Core commands

```bash
uv run pytest benchmark/tests -q
uv run ruff check .
uv run bench --help
uv run bench doctor                                 # validate env vars + runs dir
uv run bench --full --dry-run
uv run bench --full --scenario-parallel 8 -y --max-cost-usd 50
env INVISIBLEBENCH_API_TIMEOUT_SECONDS=30 INVISIBLEBENCH_API_MAX_RETRIES=1 \
  uv run bench -m deepseek --scenario context_regulatory_data_privacy_001 -y --max-cost-usd 0.10  # cheap transcript canary
uv run bench runs --limit 25 --offset 0             # list runs (paged)
uv run bench get <run-id>                           # read a single run's metadata
uv run bench --json runs                            # JSON envelope for agents
uv run bench --json runs --out /tmp/runs.json       # write full payload to file; stdout = summary envelope
uv run python scripts/lint_turn_indices.py --strict
uv run python scripts/run_scan.py results/run_... --profile dev --dry-run --enable-llm --llm-model openai/gpt-5-mini
uv run python scripts/run_scan.py results/run_... --profile publish --enable-llm --max-cost-usd 500 --llm-model openai/gpt-5-mini
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
- [docs/governance.md](docs/governance.md) — conflict-of-interest, versioning/stability, third-party submission, and annotation/ethics policy
- [SECURITY.md](SECURITY.md) — private security-advisory channel
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — Contributor Covenant v2.1
- Bugs and feature requests: [GitHub Issues](https://github.com/givecareapp/givecare-bench/issues)
