"""
Example script demonstrating how to inspect parser warnings from evaluations.

This shows how to access and use the parse_warnings field to debug judge response parsing issues.
"""
from supportbench.evaluation.evaluator import JudgeResponseParser
from supportbench.models import JudgeEvaluation, TurnEvaluation, ModelResponse, DimensionType


def demonstrate_parser_warnings():
    """Demonstrate how to access and inspect parser warnings."""
    parser = JudgeResponseParser()

    print("=" * 80)
    print("Parser Warnings Demonstration")
    print("=" * 80)
    print()

    # Example 1: Response with score exceeding max
    print("Example 1: Score Exceeding Maximum")
    print("-" * 80)
    response_1 = """
## CRISIS SAFETY: 5/3
This score exceeds the maximum.

## REGULATORY FITNESS: 3/3
Normal score.

## AUTOFAIL: No
"""
    result_1 = parser.parse_judge_response("judge_1", response_1)
    print(f"Scores parsed: {result_1['scores']}")
    print(f"Warnings: {len(result_1['parse_warnings'])}")
    for warning in result_1['parse_warnings']:
        print(f"  - {warning}")
    print()

    # Example 2: Response with missing dimensions
    print("Example 2: Missing Dimensions")
    print("-" * 80)
    response_2 = """
## CRISIS SAFETY: 2/3
Only one dimension provided.

## AUTOFAIL: No
"""
    result_2 = parser.parse_judge_response("judge_2", response_2)
    print(f"Scores parsed: {result_2['scores']}")
    print(f"Warnings: {len(result_2['parse_warnings'])}")
    for warning in result_2['parse_warnings']:
        print(f"  - {warning}")
    print()

    # Example 3: Creating JudgeEvaluation with warnings
    print("Example 3: JudgeEvaluation with Warnings")
    print("-" * 80)
    judge_eval = JudgeEvaluation(
        judge_name="judge_1",
        judge_model="test-model",
        dimension_scores=result_1["scores"],
        reasoning=result_1["reasoning"],
        autofail_triggered=result_1["autofail"],
        autofail_reason=result_1["autofail_reason"],
        raw_response=response_1,
        parse_warnings=result_1.get("parse_warnings", [])
    )
    print(f"Judge: {judge_eval.judge_name}")
    print(f"Warnings count: {len(judge_eval.parse_warnings)}")
    for warning in judge_eval.parse_warnings:
        print(f"  - {warning}")
    print()

    # Example 4: TurnEvaluation aggregating warnings from multiple judges
    print("Example 4: TurnEvaluation Aggregating Warnings")
    print("-" * 80)

    # Create multiple judge evaluations
    judge_eval_1 = JudgeEvaluation(
        judge_name="judge_1",
        judge_model="model-1",
        dimension_scores={DimensionType.CRISIS_SAFETY: 2.0},
        reasoning="Reasoning 1",
        parse_warnings=["Warning A from judge_1", "Warning B from judge_1"]
    )

    judge_eval_2 = JudgeEvaluation(
        judge_name="judge_2",
        judge_model="model-2",
        dimension_scores={DimensionType.REGULATORY_FITNESS: 3.0},
        reasoning="Reasoning 2",
        parse_warnings=["Warning C from judge_2"]
    )

    judge_eval_3 = JudgeEvaluation(
        judge_name="judge_3",
        judge_model="model-3",
        dimension_scores={DimensionType.RELATIONAL_QUALITY: 1.0},
        reasoning="Reasoning 3",
        parse_warnings=[]  # No warnings
    )

    # Create TurnEvaluation
    turn_eval = TurnEvaluation(
        turn_number=1,
        session_number=None,
        model_response=ModelResponse(
            model_name="test-model",
            response_text="Test response",
            turn_number=1
        ),
        judge_evaluations=[judge_eval_1, judge_eval_2, judge_eval_3],
        aggregated_scores={
            DimensionType.CRISIS_SAFETY: 2.0,
            DimensionType.REGULATORY_FITNESS: 3.0,
            DimensionType.RELATIONAL_QUALITY: 1.0
        }
    )

    # Get all warnings across all judges
    all_warnings = turn_eval.get_all_warnings()
    print(f"Total warnings from all judges: {len(all_warnings)}")
    for warning in all_warnings:
        print(f"  - {warning}")
    print()

    # Example 5: Checking if there are any warnings
    print("Example 5: Quick Check for Warnings")
    print("-" * 80)
    if all_warnings:
        print("⚠️  Warnings detected! Review parsing issues:")
        for warning in all_warnings:
            print(f"  - {warning}")
    else:
        print("✓ No parsing warnings - all judge responses parsed cleanly")
    print()

    print("=" * 80)
    print("Summary:")
    print(f"  - parse_warnings are now included in JudgeEvaluation")
    print(f"  - Use turn_eval.get_all_warnings() to see all warnings for a turn")
    print(f"  - Warnings help identify parsing issues like:")
    print(f"    * Scores exceeding maximum values")
    print(f"    * Missing dimensions in judge responses")
    print(f"    * Malformed scores")
    print("=" * 80)


if __name__ == "__main__":
    demonstrate_parser_warnings()
