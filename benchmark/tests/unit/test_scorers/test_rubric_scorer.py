"""v2 rubric scorer tests — JSON parsing, judge output extraction."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.v2


class TestRubricJsonParsing:
    """Test non-greedy JSON extraction in rubric scorer."""

    def test_plain_json(self):
        from invisiblebench.evaluation.scorers.rubric_scorer import _parse_judge_json

        result = _parse_judge_json('{"answer": true, "confidence": 0.9, "evidence": "good"}')
        assert result is not None
        assert result["answer"] is True

    def test_json_with_preamble(self):
        from invisiblebench.evaluation.scorers.rubric_scorer import _parse_judge_json

        text = 'Here is my evaluation {of the response}:\n{"answer": false, "confidence": 0.7, "evidence": "missed"}'
        result = _parse_judge_json(text)
        assert result is not None
        assert result["answer"] is False

    def test_json_with_braces_in_preamble(self):
        from invisiblebench.evaluation.scorers.rubric_scorer import _parse_judge_json

        text = 'The {question} asks about validation.\n{"answer": true, "confidence": 0.8, "evidence": "validated"}'
        result = _parse_judge_json(text)
        assert result is not None
        assert result["answer"] is True

    def test_no_json_returns_none(self):
        from invisiblebench.evaluation.scorers.rubric_scorer import _parse_judge_json

        result = _parse_judge_json("No JSON here at all")
        assert result is None
