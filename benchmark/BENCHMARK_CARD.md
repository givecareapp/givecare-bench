# Benchmark Card: InvisibleBench

## Basic Information
- Name: InvisibleBench
- Version: 1.2.0 (code version); scoring contract 1.1.0
- Domain: Caregiving AI safety (persistent caregiving relationships)

## Task Description
InvisibleBench evaluates multi-turn caregiver-support conversations across five dimensions:
- Safety
- Compliance
- Trauma-informed care
- Belonging
- Longitudinal memory

The benchmark supports both model-only evaluation and full-system evaluation for caregiver
assistants operating in persistent relationships.

## Dataset Characteristics
- 32 scenarios total: 29 standard + 3 confidential holdout scenarios
- 4 tiers with increasing conversation length and complexity
  - Tier 0: 1-3 turns (core safety gates)
  - Tier 1: 3-5 turns (crisis detection and gray zones)
  - Tier 2: 8-12 turns (boundary durability and relationship dynamics)
  - Tier 3: 20+ turns (multi-session longitudinal memory)
- Scenario format: JSON with persona, turns, metadata, and scoring expectations per dimension
- Confidential scenarios are excluded from public leaderboards by default

## Evaluation Methodology
- Rubric-based scoring across five dimensions with weighted aggregation
  - Belonging 0.34, Memory 0.16, Safety 0.20, Compliance 0.15, Trauma 0.15
- Scenario-level gate types include fail-closed safety gates
- Compliance hard-fail rules include diagnosis, impersonation, and missed crisis
- Hard-fails override numeric scores for the affected scenario
- LLM-assisted scoring is optional; offline scoring is supported for deterministic runs

## Limitations and Ethical Considerations
- Curated scenarios cannot fully cover the diversity of real-world caregiving contexts
- Confidential holdout scenarios limit full reproducibility and should not be used for training
- LLM-assisted scoring can introduce subjectivity; audit and human review are recommended
- Results are for safety evaluation only and are not clinical or medical advice
- Avoid storing or exporting sensitive caregiver data in evaluation transcripts
