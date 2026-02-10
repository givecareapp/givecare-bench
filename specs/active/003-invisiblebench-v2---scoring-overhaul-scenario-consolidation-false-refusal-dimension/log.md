# Log: InvisibleBench v2 — Scoring Overhaul, Scenario Consolidation, False Refusal Dimension

## 2026-02-10
- Spec created
- Research completed: HEART, MentalBench, MultiChallenge, MindEval benchmarks
- Key finding: instance-level rubric scoring (MultiChallenge) achieves 93% human agreement vs 36% for holistic LLM-as-judge
- Key finding: cognitive-affective gap (MentalBench) — LLM judges unreliable for empathy/safety dimensions
- Key finding: false refusal escalation 8→25→75% across GPT generations ("When Better Means Less")
- 4 false_refusal scenarios already created (medication_side_effects, hospice_what_to_expect, grief_after_loss, end_of_life_planning)
