"""Minimal example using the YAML orchestrator to score a transcript."""

from invisiblebench.evaluation.orchestrator import ScoringOrchestrator


def main() -> None:
    orchestrator = ScoringOrchestrator(
        scoring_config_path="benchmark/configs/scoring.yaml",
        enable_state_persistence=False,
        enable_llm=False,
    )

    results = orchestrator.score(
        transcript_path="benchmark/tests/fixtures/sample_transcript.jsonl",
        scenario_path="benchmark/scenarios/safety/crisis/cssrs_passive_ideation.json",
        rules_path="benchmark/configs/rules/base.yaml",
    )

    print("Overall Score:", results["overall_score"])
    print("Dimension Scores:", results["dimension_scores"])


if __name__ == "__main__":
    main()
