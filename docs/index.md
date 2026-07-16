# InvisibleBench

**InvisibleBench** is a public safety benchmark for multi-turn caregiver-support AI.
It evaluates whether language models can safely and effectively support family caregivers
across realistic multi-turn conversations.

!!! note "Current result status"
    The checked-in v4 scorecard is a historical research snapshot. Its source
    merge predates the current v2 provenance contract, so it does not pass the
    current strict publication gate. Safety claims remain calibration-gated;
    Care results remain directional.

## Scoring model

InvisibleBench uses a two-layer **Safety + Care** model. There is no composite score. The two layers are reported side by side; they are never merged.

**Safety** — 4 lines (Crisis, Scope, Identity, Autonomy) reported as per-line **conditional violation rates** (numerator = eligible scenarios where the hard line was crossed; denominator = eligible scenarios). A Safety violation on any calibrated check blocks publication.

**Care** — 5 qualities (Belonging, Attunement, Trauma-awareness, Relational, Advocacy) reported as **directional pass-rate distributions**, not averaged into a single number. Each quality reflects a different facet of how the AI shows up for the caregiver.

!!! info "No composite, no rank"
    There is no `overall_score` and no single leaderboard rank. The leaderboard payload is `{safety, care}` (schema `safety-care/v1`). The design forces model-by-model audit rather than stack ranking.

Canonical model: [ontology.md](ontology.md). Positioning and the three moats: [what-invisiblebench-owns.md](what-invisiblebench-owns.md).

## Key facts

- **Current public corpus** covers 63 scenarios across 4 categories
- **50 checks across 9 dimensions** — 4 Safety lines + 5 Care qualities — with binary `claim_ready` / `not_claim_ready` calibration status (currently 0 `claim_ready`)
- **Multi-turn with conditional branching** — adaptive evaluation paths based on model responses
- Machine-readable inventory, versions, roster, and prices are read from the
  benchmark inventory, version module, model catalog, and dry-run plans
- Public harness: `llm/raw`

## Publication posture

The public web-bench story is a model-by-model audit, not a stack rank. The
release flow first documents the benchmark mechanics, then projects the scored
outputs into per-model audit cards: per-line Safety violation rates (claim-
bearing only for `claim_ready` checks, currently empty) and directional Care
distributions (`not_claim_ready`). There is no
composite and no rank. The richer narrative surface — thematic blind spots,
contrastive pairs, model signatures — is deferred to a re-authored Safety/Care
artifact-v2 and is not in the lean `safety-care/v1` payload. See
[Benchmark Publishing Audit](publishing-audit.md).

## Quick start

```bash
# See available commands
uv run bench --help

# Validate env vars + runs dir before a run
uv run bench doctor

# Full dry-run (no LLM calls)
uv run bench --full --dry-run

# List benchmark runs (paged; default limit 25)
uv run bench runs --limit 25 --offset 0

# Read metadata for a single run (exact id or prefix match)
uv run bench get <run-id>

# JSON envelope for agent consumers (wraps runs / stats / leaderboard)
uv run bench --json runs

# Write full payload to disk; stdout gets a summary envelope
uv run bench --json runs --out /tmp/runs.json

# Run unit tests
uv run pytest benchmark/tests -q
```

!!! tip "Agent-friendly CLI"
    Both `bench` and `invisiblebench` respect `NO_COLOR=1`, emit a
    `{status, command, data}` envelope under `--json` / `--format json`, and
    support paging. The YAML entry point also ships `invisiblebench --doctor`
    and `invisiblebench --list-runs --limit N --offset M`. `--out PATH` (on
    `runs`, `get`, and `leaderboard status`) writes the full payload to disk
    and emits a `{path, byte_count, record_count}` summary. `leaderboard
    add/rebuild` is retired for `safety-care/v1`; publish from an explicit
    scored scan JSONL and web target via the fail-closed generate → strict QA → sync chain. Archive
    writes refuse in non-interactive shells unless `--yes` is passed.

## Documentation

- [Install](install.md) — how to put `bench` and `invisiblebench` on PATH
- [Scoring Rubric](scoring-rubric.md) — full scoring weights, dimension definitions, gate logic
- [Architecture](architecture.md) — system design, scenario schema, harness pipeline
- [Methodology](methodology.md) — framework grounding, research mapping, regulatory landscape
- [Publishing Audit](publishing-audit.md) — two-phase publication model and web-bench narrative contract
- [Ontology](ontology.md) — **canonical** Safety + Care output model (SAMHSA + Microsoft Inclusive Design + OBI framework grounding)
- [Taxonomy](taxonomy.md) — thin reference: per-dimension check-count table (the model itself is in ontology.md)
- [Verifier Validation](verifier-validation.md) — verifier manifest, the binary claim model, and the `claim_ready` bar
- [Verifier Unit Tests](verifier-unit-tests.md) — authored AI-panel spec-conformance tests (development, **not** validation)
