# Benchmark Card: InvisibleBench

## Basic Information
- Name: InvisibleBench
- Version: 2.0.0 (code version); scoring contract 2.0.0
- Domain: Caregiving AI safety (persistent caregiving relationships)

## Task Description
InvisibleBench evaluates multi-turn caregiver-support conversations across seven dimensions:
- Safety
- Compliance
- Attunement (trauma-informed flow)
- Belonging
- False Refusal
- Longitudinal memory
- Intra-conversation consistency

The benchmark supports both model-only evaluation and full-system evaluation for caregiver
assistants operating in persistent relationships.

## Dataset Characteristics
- 38 scenarios total: 35 standard + 3 confidential holdout scenarios
- 25 additional archived scenarios available via `--include-archive`
- 4 MECE capability categories:
  - Safety: 12 scenarios (crisis detection, gray zones, boundaries, false refusal)
  - Empathy: 10 scenarios (burnout, belonging, grief, relational dynamics)
  - Context: 9 scenarios (cultural sensitivity, regulatory compliance)
  - Continuity: 4 scenarios (multi-session longitudinal memory)
- Scenario format: JSON with persona, turns, metadata, and scoring expectations per dimension
- Confidential scenarios are excluded from public leaderboards by default
- Default evaluation runs 35 standard scenarios

## Evaluation Methodology
- Rubric-based scoring across seven dimensions with weighted aggregation
  - Safety 0.20, Compliance 0.15, Attunement 0.15, Belonging 0.31, False Refusal 0.03, Memory 0.11, Consistency 0.05
- Scenario-level gate types include fail-closed safety gates
- Compliance hard-fail rules include diagnosis, impersonation, and missed crisis
- Hard-fails override numeric scores for the affected scenario
- LLM-assisted scoring is optional; offline scoring is supported for deterministic runs
- Conditional branching: 4 scenarios adapt user messages based on model behavior using deterministic conditions (keyword/regex matching), testing failure recovery and escalation patterns

## Limitations and Ethical Considerations
- Curated scenarios cannot fully cover the diversity of real-world caregiving contexts
- Confidential holdout scenarios limit full reproducibility and should not be used for training
- LLM-assisted scoring can introduce subjectivity; audit and human review are recommended
- Results are for safety evaluation only and are not clinical or medical advice
- Avoid storing or exporting sensitive caregiver data in evaluation transcripts
- Conditional branching introduces path variability: branched scenarios may produce different transcripts depending on model behavior, which is intentional but means exact transcript reproducibility depends on model determinism
