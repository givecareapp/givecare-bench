"""The published checks load, and their identity comes from their file path."""

from __future__ import annotations

from pathlib import Path

import pytest

from invisiblebench.evaluation.check_registry import load_check, load_checks
from invisiblebench.models.scan import DIMENSIONS, Question

CHECKS_DIR = Path(__file__).resolve().parents[3] / "checks"
EXPECTED_CHECKS = 49


def test_the_published_directory_holds_every_check():
    """The real corpus, not the fixture registry the rest of the suite uses."""
    checks = load_checks(CHECKS_DIR)
    assert len(checks) == EXPECTED_CHECKS
    for check_id, check in checks.items():
        assert check_id == check.id
        assert check.dimension in DIMENSIONS[check.layer]
        assert check.id.startswith(check.dimension + ".")
        assert check.fail_if or check.pass_if_any


def test_a_check_id_must_equal_its_file_name(tmp_path):
    path = tmp_path / "crisis.renamed.yaml"
    path.write_text(
        "id: crisis.fixture\nname: fixture\nseverity: S5\nsummary: A fixture check.\n"
        "questions:\n  routing:\n    instructions: Does `assistant` route?\n"
        "fail_if:\n  - {question: routing, is: false}\n"
    )
    with pytest.raises(ValueError, match="does not match its file name"):
        load_check(path)


def test_an_empty_directory_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_checks(tmp_path)


@pytest.mark.parametrize("kind", ["noul", "choice"])
def test_criteria_follow_question_type_through_json_roundtrip(kind):
    criteria = {"true": "The condition holds.", "false": "The condition does not hold."}
    question = Question.model_validate({"type": kind, "instructions": "Does it hold?", "criteria": criteria})
    assert question.criteria == criteria
    assert question.model_dump(mode="json")["criteria"] == criteria
    assert Question.model_validate_json(question.model_dump_json()) == question


@pytest.mark.parametrize("criteria", [{"true": "Yes"}, {"yes": "Yes", "no": "No"}, {"true": "Yes", "false": "No", "other": "Other"}])
def test_noul_rejects_incomplete_or_unknown_criteria(criteria):
    with pytest.raises(ValueError):
        Question.model_validate({"instructions": "Does it hold?", "criteria": criteria})
