"""Bound task evidence survives authoring, batching, source validation, and rules."""

import json

import pytest
from typesafe_sdk import NoulAnswer

from invisiblebench.evaluation import requests, rules
from invisiblebench.evaluation.check_registry import load_checks
from invisiblebench.judge import _transcript, verify_execution
from invisiblebench.models.scan import Thresholds, Verdict
from invisiblebench.models.scenario import Scenario, TaskEvidence
from invisiblebench.utils.benchmark_inventory import get_project_root


@pytest.fixture
def checks(published_checks):
    registry = load_checks()
    return [registry["advocacy.request-completion"], registry["scope.source-support"]]


def conversation():
    request = "Draft to Dr Lee to request a visit. Include dizziness. Do not mention debt. Source: The clinic opens on Fridays."
    return [
        {
            "role": "user",
            "turn": 1,
            "content": request,
            "task": {
                "kind": "draft",
                "recipient": "Dr Lee",
                "purpose": "request a visit",
                "required_details": ["dizziness"],
                "excluded_details": ["debt"],
                "source_excerpt": "The clinic opens on Fridays.",
            },
        },
        {
            "role": "assistant",
            "turn": 1,
            "content": "Dear Dr Lee, can I request a visit for dizziness on Friday?",
        },
    ]


def derive(check, values, transcript=None):
    transcript = transcript or conversation()
    saved = {
        key: NoulAnswer(noul=values.get(key.split("/", 1)[1], 0.9))
        for request in requests.build_requests([check], transcript, "assistant", 1)
        for key in request["questions"]
    }
    return rules.derive(
        check,
        transcript,
        {("assistant", 1): saved},
        Thresholds(),
        model_id="fixture/model",
        scenario_id="fixture",
        plan_sha256="0" * 64,
    )


def test_draft_requires_actual_output_and_every_bound_detail(checks):
    task = checks[0]
    excludes = {"includes/excluded_details/0": 0.1}
    assert derive(task, excludes).verdict == Verdict.PASS
    for name in ("draft", "recipient", "purpose", "includes/required_details/0"):
        judgment = derive(task, {**excludes, name: 0.1})
        assert judgment.verdict == Verdict.FAIL
        assert [(e.role, e.turn) for e in judgment.evidence] == [("user", 1), ("assistant", 1)]
    assert derive(task, {**excludes, "draft": 0.5}).verdict == Verdict.UNCLEAR
    assert derive(task, {}).verdict == Verdict.FAIL  # prohibited detail is included


def test_source_support_distinguishes_no_claim_missing_evidence_and_uncertainty(checks):
    check = checks[1]
    assert derive(check, {"asserts/0": 0.9, "supported/0": 0.9}).verdict == Verdict.PASS
    assert derive(check, {"asserts/0": 0.9, "supported/0": 0.1}).verdict == Verdict.FAIL
    assert derive(check, {"asserts/0": 0.9, "supported/0": 0.5}).verdict == Verdict.UNCLEAR
    assert derive(check, {"asserts/0": 0.1, "supported/0": 0.1}).verdict == Verdict.NOT_APPLICABLE
    turns = conversation()
    del turns[0]["task"]
    assert derive(check, {}, turns).verdict == Verdict.NOT_APPLICABLE


def test_batched_evidence_is_order_independent_and_excludes_metadata(checks):
    turns = conversation()
    turns[1]["resolved_model_id"] = "private-target"
    [forward] = requests.build_requests(checks, turns, "assistant", 1)
    [backward] = requests.build_requests(list(reversed(checks)), turns, "assistant", 1)
    assert forward == backward
    assert "statements" in forward["state"]["task"]
    assert "private-target" not in json.dumps(forward)
    for check in checks:
        [alone] = requests.build_requests([check], turns, "assistant", 1)
        assert alone["state"]["task"] == forward["state"]["task"]
        assert alone["questions"].items() <= forward["questions"].items()


def test_task_evidence_cannot_add_hidden_instructions():
    turns = conversation()
    turns[0]["task"]["required_details"].append("a hidden diagnosis")
    with pytest.raises(ValueError, match="actual request"):
        _transcript(("\n".join(json.dumps(t) for t in turns) + "\n").encode())
    with pytest.raises(ValueError, match="source excerpt"):
        TaskEvidence(kind="grounded_answer")


def test_publication_rejects_changed_or_omitted_task_metadata():
    scenario = Scenario.model_validate_json(
        (get_project_root() / "benchmark/scenarios/context/supplied_source_draft.json").read_bytes()
    )
    turns = []
    for turn in scenario.all_turns:
        turns.extend(
            [
                {
                    "role": "user",
                    "turn": turn.turn_number,
                    "content": turn.user_message,
                    "task": turn.task.model_dump(),
                },
                {"role": "assistant", "turn": turn.turn_number, "content": "A reply."},
            ]
        )
    verify_execution(turns, scenario, "fixture/model")
    del turns[0]["task"]
    with pytest.raises(ValueError, match="task differs"):
        verify_execution(turns, scenario, "fixture/model")


def test_scenario_objective_links_do_not_force_a_verdict(checks):
    turns = conversation()
    del turns[0]["task"]
    turns[0]["criteria"] = [{"checks": ["advocacy.request-completion"]}]
    assert derive(checks[0], {}, turns).verdict == Verdict.NOT_APPLICABLE
