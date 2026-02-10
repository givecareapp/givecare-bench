"""Tests for conditional branching in adaptive multi-turn scenarios."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from invisiblebench.evaluation.branching import resolve_branch

# ---------------------------------------------------------------------------
# resolve_branch — basic behaviour
# ---------------------------------------------------------------------------


class TestResolveBranchDefaults:
    """When no branches exist or no prior response, the default message is used."""

    def test_no_branches_key(self) -> None:
        turn = {"turn_number": 1, "user_message": "Hello"}
        msg, bid = resolve_branch(turn, "some response")
        assert msg == "Hello"
        assert bid is None

    def test_empty_branches_list(self) -> None:
        turn = {"turn_number": 2, "user_message": "Default", "branches": []}
        msg, bid = resolve_branch(turn, "some response")
        assert msg == "Default"
        assert bid is None

    def test_no_prior_response(self) -> None:
        turn = {
            "turn_number": 1,
            "user_message": "First message",
            "branches": [
                {
                    "branch_id": "x",
                    "condition": {"type": "contains_any", "values": ["hello"]},
                    "user_message": "Branched",
                }
            ],
        }
        msg, bid = resolve_branch(turn, None)
        assert msg == "First message"
        assert bid is None


# ---------------------------------------------------------------------------
# contains_any
# ---------------------------------------------------------------------------


class TestContainsAny:
    def _turn(self, values: list[str]) -> dict:
        return {
            "turn_number": 2,
            "user_message": "Default path",
            "branches": [
                {
                    "branch_id": "matched",
                    "condition": {"type": "contains_any", "values": values},
                    "user_message": "Branch taken",
                }
            ],
        }

    def test_keyword_present(self) -> None:
        msg, bid = resolve_branch(self._turn(["dose", "mg"]), "Take 5mg every 6 hours")
        assert msg == "Branch taken"
        assert bid == "matched"

    def test_case_insensitive(self) -> None:
        msg, bid = resolve_branch(self._turn(["988"]), "Please call 988 Lifeline")
        assert msg == "Branch taken"

    def test_no_keyword_present(self) -> None:
        msg, bid = resolve_branch(self._turn(["dose", "mg"]), "I understand your concern")
        assert msg == "Default path"
        assert bid is None


# ---------------------------------------------------------------------------
# contains_all
# ---------------------------------------------------------------------------


class TestContainsAll:
    def _turn(self, values: list[str]) -> dict:
        return {
            "turn_number": 2,
            "user_message": "Default",
            "branches": [
                {
                    "branch_id": "all_match",
                    "condition": {"type": "contains_all", "values": values},
                    "user_message": "All matched",
                }
            ],
        }

    def test_all_present(self) -> None:
        msg, bid = resolve_branch(
            self._turn(["crisis", "988"]),
            "This sounds like a crisis. Please call 988.",
        )
        assert msg == "All matched"
        assert bid == "all_match"

    def test_partial_present(self) -> None:
        msg, bid = resolve_branch(
            self._turn(["crisis", "988"]),
            "This sounds like a crisis.",
        )
        assert msg == "Default"
        assert bid is None


# ---------------------------------------------------------------------------
# not_contains
# ---------------------------------------------------------------------------


class TestNotContains:
    def _turn(self, values: list[str]) -> dict:
        return {
            "turn_number": 9,
            "user_message": "Default",
            "branches": [
                {
                    "branch_id": "no_memory",
                    "condition": {"type": "not_contains", "values": values},
                    "user_message": "You forgot me",
                }
            ],
        }

    def test_none_present(self) -> None:
        msg, bid = resolve_branch(
            self._turn(["Jamie", "River", "disability"]),
            "I'm sorry to hear you're struggling. Can you tell me more?",
        )
        assert msg == "You forgot me"
        assert bid == "no_memory"

    def test_one_present(self) -> None:
        msg, bid = resolve_branch(
            self._turn(["Jamie", "River", "disability"]),
            "Welcome back, Jamie. I remember our last conversation.",
        )
        assert msg == "Default"
        assert bid is None


# ---------------------------------------------------------------------------
# regex
# ---------------------------------------------------------------------------


class TestRegex:
    def _turn(self, pattern: str) -> dict:
        return {
            "turn_number": 7,
            "user_message": "Default",
            "branches": [
                {
                    "branch_id": "regex_match",
                    "condition": {"type": "regex", "pattern": pattern},
                    "user_message": "Regex matched",
                }
            ],
        }

    def test_match(self) -> None:
        msg, bid = resolve_branch(
            self._turn(r"always be here|always here for you|I'm your friend"),
            "I'll always be here for you, Miguel.",
        )
        assert msg == "Regex matched"
        assert bid == "regex_match"

    def test_no_match(self) -> None:
        msg, bid = resolve_branch(
            self._turn(r"always be here|always here for you|I'm your friend"),
            "You can reach out whenever you'd like.",
        )
        assert msg == "Default"
        assert bid is None

    def test_case_insensitive(self) -> None:
        msg, bid = resolve_branch(
            self._turn(r"i'm your friend"),
            "I'M YOUR FRIEND and I care.",
        )
        assert msg == "Regex matched"


# ---------------------------------------------------------------------------
# Unknown condition type
# ---------------------------------------------------------------------------


class TestUnknownCondition:
    def test_raises(self) -> None:
        turn = {
            "turn_number": 1,
            "user_message": "Default",
            "branches": [
                {
                    "branch_id": "bad",
                    "condition": {"type": "unknown_type", "values": []},
                    "user_message": "Nope",
                }
            ],
        }
        with pytest.raises(ValueError, match="Unknown branch condition type"):
            resolve_branch(turn, "anything")


# ---------------------------------------------------------------------------
# First-match-wins ordering
# ---------------------------------------------------------------------------


class TestBranchOrdering:
    def test_first_match_wins(self) -> None:
        turn = {
            "turn_number": 3,
            "user_message": "Default",
            "branches": [
                {
                    "branch_id": "first",
                    "condition": {"type": "contains_any", "values": ["hello"]},
                    "user_message": "First branch",
                },
                {
                    "branch_id": "second",
                    "condition": {"type": "contains_any", "values": ["hello", "world"]},
                    "user_message": "Second branch",
                },
            ],
        }
        msg, bid = resolve_branch(turn, "hello world")
        assert bid == "first"
        assert msg == "First branch"


# ---------------------------------------------------------------------------
# Integration: verify actual scenario files have valid branch structure
# ---------------------------------------------------------------------------


BRANCHED_SCENARIOS = [
    "benchmark/scenarios/tier1/boundaries/medical_boundary_violation.json",
    "benchmark/scenarios/tier1/gray_zone/venting_vs_crisis.json",
    "benchmark/scenarios/tier1/crisis/crisis_recovery_test.json",
    "benchmark/scenarios/tier2/longitudinal/attachment_formation.json",
    "benchmark/scenarios/tier3/longitudinal_trust.json",
]


@pytest.mark.parametrize("scenario_path", BRANCHED_SCENARIOS)
def test_scenario_branch_schema(scenario_path: str) -> None:
    """Each branched scenario file has valid branch structure."""
    repo_root = Path(__file__).resolve().parents[3]
    full_path = repo_root / scenario_path
    if not full_path.exists():
        pytest.skip(f"Scenario not found: {full_path}")

    with open(full_path) as f:
        data = json.load(f)

    # Collect all turns (flat or multi-session)
    all_turns = []
    if "sessions" in data:
        for session in data["sessions"]:
            all_turns.extend(session.get("turns", []))
    else:
        all_turns = data.get("turns", [])

    branch_count = 0
    for turn in all_turns:
        branches = turn.get("branches")
        if not branches:
            continue
        for branch in branches:
            branch_count += 1
            assert "branch_id" in branch, f"Missing branch_id in turn {turn['turn_number']}"
            assert "condition" in branch, f"Missing condition in turn {turn['turn_number']}"
            assert "user_message" in branch, f"Missing user_message in turn {turn['turn_number']}"
            cond = branch["condition"]
            assert "type" in cond, f"Missing condition type in turn {turn['turn_number']}"
            assert cond["type"] in (
                "contains_any",
                "contains_all",
                "not_contains",
                "regex",
            ), f"Invalid condition type: {cond['type']}"

    assert branch_count > 0, f"No branches found in {scenario_path}"
