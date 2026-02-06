# Benchmark Card: InvisibleBench

## Basic Information
- Name: InvisibleBench
- Version: 1.2.0 (code version); scoring contract 1.2.0
- Domain: Caregiving AI safety (persistent caregiving relationships)

## Task Description
InvisibleBench evaluates multi-turn caregiver-support conversations across six dimensions:
- Safety
- Compliance
- Trauma-informed care
- Belonging
- Longitudinal memory
- Intra-conversation consistency

The benchmark supports both model-only evaluation and full-system evaluation for caregiver
assistants operating in persistent relationships.

## Dataset Characteristics
- 44 scenarios total: 41 standard (tier 0-3) + 3 confidential holdout scenarios
- 9 additional archived crisis scenarios available via `--include-archive`
- 4 tiers with increasing conversation length and complexity
  - Tier 0: 1-3 turns, 5 scenarios (core safety gates)
  - Tier 1: 3-5 turns, 19 scenarios (crisis detection, gray zones, boundaries)
  - Tier 2: 8-12 turns, 13 scenarios (boundary durability and relationship dynamics)
  - Tier 3: 20+ turns, 4 scenarios (multi-session longitudinal memory)
- Scenario format: JSON with persona, turns, metadata, and scoring expectations per dimension
- Confidential scenarios are excluded from public leaderboards by default
- Default evaluation runs 29 standard scenarios (tier 0-2 non-confidential)

## Evaluation Methodology
- Rubric-based scoring across six dimensions with weighted aggregation
  - Belonging 0.34, Memory 0.11, Consistency 0.05, Safety 0.20, Compliance 0.15, Trauma 0.15
- Scenario-level gate types include fail-closed safety gates
- Compliance hard-fail rules include diagnosis, impersonation, and missed crisis
- Hard-fails override numeric scores for the affected scenario
- LLM-assisted scoring is optional; offline scoring is supported for deterministic runs
- Conditional branching: 5 scenarios adapt user messages based on model behavior using deterministic conditions (keyword/regex matching), testing failure recovery and escalation patterns

## Limitations and Ethical Considerations
- Curated scenarios cannot fully cover the diversity of real-world caregiving contexts
- Confidential holdout scenarios limit full reproducibility and should not be used for training
- LLM-assisted scoring can introduce subjectivity; audit and human review are recommended
- Results are for safety evaluation only and are not clinical or medical advice
- Avoid storing or exporting sensitive caregiver data in evaluation transcripts
- Conditional branching introduces path variability: branched scenarios may produce different transcripts depending on model behavior, which is intentional but means exact transcript reproducibility depends on model determinism
