"""
Integration test to verify parse warnings are surfaced in evaluation results.
"""
from invisiblebench.evaluation.evaluator import JudgeResponseParser
from invisiblebench.models import DimensionType, JudgeEvaluation, ModelResponse, TurnEvaluation


class TestWarningsIntegration:
    """Test that parser warnings flow through the evaluation pipeline."""

    def test_warnings_in_judge_evaluation(self):
        """Test that parse warnings are captured in JudgeEvaluation."""
        parser = JudgeResponseParser()

        # Response with score exceeding max (triggers warning)
        response = """
## CRISIS SAFETY: 5/3
This should trigger a warning.

## AUTOFAIL: No
"""

        result = parser.parse_judge_response("judge_1", response)

        # Create JudgeEvaluation with warnings
        judge_eval = JudgeEvaluation(
            judge_name="judge_1",
            judge_model="test-model",
            dimension_scores=result["scores"],
            reasoning=result["reasoning"],
            autofail_triggered=result["autofail"],
            autofail_reason=result["autofail_reason"],
            raw_response=response,
            parse_warnings=result.get("parse_warnings", [])
        )

        # Verify warnings are present
        assert len(judge_eval.parse_warnings) > 0
        assert any("exceeds max" in w for w in judge_eval.parse_warnings)

    def test_warnings_aggregation_in_turn_evaluation(self):
        """Test that TurnEvaluation can aggregate warnings from all judges."""
        # Create mock judge evaluations with warnings
        judge_eval_1 = JudgeEvaluation(
            judge_name="judge_1",
            judge_model="test-model-1",
            dimension_scores={DimensionType.CRISIS_SAFETY: 2.0},
            reasoning="Test reasoning 1",
            parse_warnings=["[judge_1] CRISIS SAFETY: score 5 exceeds max 3"]
        )

        judge_eval_2 = JudgeEvaluation(
            judge_name="judge_2",
            judge_model="test-model-2",
            dimension_scores={DimensionType.REGULATORY_FITNESS: 3.0},
            reasoning="Test reasoning 2",
            parse_warnings=["[judge_2] TRAUMA_INFORMED_FLOW not found in response"]
        )

        judge_eval_3 = JudgeEvaluation(
            judge_name="judge_3",
            judge_model="test-model-3",
            dimension_scores={DimensionType.RELATIONAL_QUALITY: 1.0},
            reasoning="Test reasoning 3",
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

        # Test get_all_warnings method
        all_warnings = turn_eval.get_all_warnings()

        # Verify warnings are aggregated correctly
        assert len(all_warnings) == 2  # Two judges had warnings
        assert any("judge_1" in w and "exceeds max" in w for w in all_warnings)
        assert any("judge_2" in w and "not found" in w for w in all_warnings)

    def test_empty_warnings_handling(self):
        """Test that empty warnings are handled gracefully."""
        # Create JudgeEvaluation with no warnings (using default)
        judge_eval = JudgeEvaluation(
            judge_name="judge_1",
            judge_model="test-model",
            dimension_scores={DimensionType.CRISIS_SAFETY: 2.0},
            reasoning="Test reasoning"
        )

        # Should have empty list by default
        assert judge_eval.parse_warnings == []

        # Create TurnEvaluation with no warnings
        turn_eval = TurnEvaluation(
            turn_number=1,
            session_number=None,
            model_response=ModelResponse(
                model_name="test-model",
                response_text="Test response",
                turn_number=1
            ),
            judge_evaluations=[judge_eval],
            aggregated_scores={DimensionType.CRISIS_SAFETY: 2.0}
        )

        # Should return empty list
        all_warnings = turn_eval.get_all_warnings()
        assert all_warnings == []

    def test_warnings_with_multiple_parse_issues(self):
        """Test that multiple warnings per judge are all captured."""
        parser = JudgeResponseParser()

        # Response with multiple issues:
        # - Score exceeds max
        # - Missing dimensions
        response = """
## CRISIS SAFETY: 10/3
Invalid high score.

## AUTOFAIL: No
"""

        result = parser.parse_judge_response("judge_test", response)

        # Should have multiple warnings
        assert len(result["parse_warnings"]) > 1

        # Should have warning about score exceeding max
        assert any("exceeds max" in w for w in result["parse_warnings"])

        # Should have warnings about missing dimensions
        missing_warnings = [w for w in result["parse_warnings"] if "not found" in w]
        assert len(missing_warnings) > 0
