# Architecture

InvisibleBench is a multi-dimensional evaluation suite for AI caregiving assistants.
This page describes the repo layout, scoring pipeline, scenario format, and key design decisions.

## Repo layout

The codebase separates five concerns:

```
givecare-bench/
├── benchmark/           # Public corpus — data only, no runtime code
│   ├── scenarios/       # 50 scenario JSON files
│   ├── configs/         # Scoring weights, prompts, jurisdiction rules
│   └── tests/           # Unit tests for schema and scoring contracts
├── src/invisiblebench/  # Runtime package (CLI, scorers, loaders, adapters, stats)
├── scripts/             # Active utilities (benchmark maintenance + verifier tooling)
├── data/leaderboard/    # Generated public artifacts (JSON, HTML)
└── archive/             # Historical docs, scripts, and remediation bundles
```

| Directory | Contents | Changes often? |
|-----------|----------|---------------|
| `benchmark/` | Scenario JSON, scoring config, judge prompts, jurisdiction rules, tests | Rarely — versioned contract |
| `src/invisiblebench/` | CLI entry point, scorer implementations, YAML/JSON loaders, adapter bridges, statistical analysis | Yes — runtime logic |
| `scripts/` | Active utilities such as `generate_leaderboard.py`, `lint_turn_indices.py`, `generate_verifier_corpus.py`, and golden-set tooling | Occasionally |
| `data/leaderboard/` | Published leaderboard JSON consumed by the docs site | Generated — never hand-edited |
| `archive/` | Superseded docs, one-off scripts, and historical internal remediation artifacts | Rarely |

## Scoring pipeline

Every evaluation run follows a single data flow:

```
scenario JSON ──► harness (transcript generation) ──► scorer pipeline ──► results ──► leaderboard
```

The scorer pipeline applies five runtime scorers. Safety and compliance are fail-closed gates; regard and coordination provide quality scores; memory is a supporting deterministic signal.

### Safety gate

Deterministic pattern checks run first. An LLM judge then evaluates crisis detection,
harm prevention, and appropriate escalation. A hard failure here zeroes the overall score.

### Compliance gate

Three-phase design:

1. **Regex candidates** — fast pattern match flags potential violations
2. **Structured LLM confirmation** — judge reviews each candidate in context with typed fields
3. **LLM sweep** — catch-all pass for violations the regex missed

The gate hard-fails on diagnosis, patient-specific prescribing/treatment directives, and false scope/capability claims (for example: invented confidentiality, deletion, or memory guarantees). It deliberately preserves allowed practical caregiving support and general/public medication information unless the model crosses into patient-specific clinical action.

### Regard scorer

LLM judge evaluates four sub-dimensions: empathy, dignity, autonomy respect, and
cultural sensitivity. Each sub-dimension is scored independently and averaged.

### Coordination scorer

Primarily deterministic. Checks whether the model correctly identifies handoff needs,
provides appropriate resource references, and avoids scope overreach.

### Memory scorer

Fully deterministic. Verifies cross-turn recall of names, conditions, preferences,
and prior conversation context using exact-match and fuzzy-match probes.

!!! info "Scoring weights and comparability"
    Default weights and per-dimension overrides live in
    `benchmark/configs/scoring.yaml` and `benchmark/configs/scoring_system.yaml`.
    Judge metadata stores stable template hashes for comparability, rather than
    hashes of fully rendered scenario-specific prompts.

## Scenario structure

Each scenario is a JSON file containing:

- **Persona** — caregiver profile (role, care recipient, stressors)
- **Turns** — ordered user messages with expected behaviors and optional rubric blocks
- **Conditional branches** — adaptive paths triggered by model response patterns
- **Probes** — targeted follow-ups that test specific scorer dimensions

Turn-level evaluation can be authored in three forms:
- prose expectations via `expected_behaviors` / `autofail_triggers`
- binary rubric items via `rubric` / `autofail_rubric`
- ordinal rubric items via `rubric_criteria`

The 50 public scenarios span four categories:

| Category | Count | Focus |
|----------|-------|-------|
| Safety | 20 | Crisis detection, harm prevention, escalation |
| Empathy | 15 | Emotional attunement, cultural sensitivity, regard |
| Context | 11 | Compliance, jurisdiction, scope boundaries |
| Continuity | 4 | Longitudinal memory, trust regression |

!!! note "Conditional branching"
    22 of the 50 scenarios contain branch points. The harness selects a branch
    based on the model's prior response, enabling adaptive evaluation without
    leaking expected answers.

## System harnesses

The public leaderboard contract accepts only the `llm/raw` harness, which sends
scenario turns directly to the model API and captures raw completions.

!!! warning "Experimental adapters"
    `givecare/live` and `givecare/orchestrator` are internal adapters that route
    through the GiveCare production stack. They share the scenario and scoring core
    but are **not** part of the public leaderboard contract.

## Jurisdiction rules

`benchmark/configs/rules/` contains per-jurisdiction compliance rule sets:

| File | Scope |
|------|-------|
| `base.yaml` | Universal baseline rules |
| `federal.yaml` | US federal (HIPAA, ADA) |
| `ca.yaml` | California-specific (CCPA, mandated reporting) |
| `ny.yaml` | New York-specific |
| `tx.yaml` | Texas-specific |
| `eu.yaml` | EU (GDPR, AI Act) |

The compliance scorer loads the applicable rule set based on the scenario's
`jurisdiction` field and evaluates against that rule set's requirements.
