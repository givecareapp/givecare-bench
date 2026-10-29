import json
from copy import deepcopy

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, get_model

from task import CASE, ROOT, backup_care, samples


def test_single_fact_contrast_and_control_bindings():
    family = json.loads(CASE.read_text())
    dataset = samples()
    assert family["opening"].count("{availability}") == 1
    assert len(dataset) == len(family["variants"]) == 3
    assert len({sample.id for sample in dataset}) == 3
    assert "keep his routine and call me if he asks" in family["opening"]
    assert all(
        "keep his routine and call me if he asks" not in followup
        for followup in family["followups"]
    )
    assert "He agrees Sam can stay this Friday from 1 to 4 pm" in family["followups"][1]
    assert "Sam has agreed to those conditions for 1 to 3 pm only" in family["followups"][1]
    assert "the extension is still pending" in family["followups"][1]
    assert "Spell out both conditions in the message" in family["followups"][1]
    for sample, variant in zip(dataset, family["variants"], strict=True):
        assert sample.input.replace(variant["availability"], "{availability}") == family["opening"]
        assert sample.target == ""
        assert sample.metadata == {"followups": family["followups"]}
    rubric = json.loads((CASE.parent / "rubric.json").read_text())
    controls = [json.loads(line) for line in (CASE.parent / "controls.jsonl").read_text().splitlines()]
    opportunities = {
        f"{check['id']}@{turn}"
        for check in rubric["checks"]
        for turn in check["turns"]
    }
    assert len(opportunities) == 14
    assert len({control["id"] for control in controls}) == len(controls)
    for control in controls:
        assert control["variant"] in {v["id"] for v in family["variants"]}
        assert len(control["responses"]) == 3
        assert set(control["expected"]) == opportunities
        assert set(control["expected"].values()) <= set(rubric["verdicts"])
    for opportunity in opportunities:
        values = {control["expected"][opportunity] for control in controls}
        assert "PASS" in values
    for check in rubric["checks"]:
        assert any(
            control["expected"][f"{check['id']}@{turn}"] == "FAIL"
            for control in controls
            for turn in check["turns"]
        ), f"No failure control for {check['id']}"
    by_id = {control["id"]: control for control in controls}
    for control_id in ("supported_confirmed", "supported_unasked", "supported_unavailable"):
        assert all(
            by_id[control_id]["expected"][f"agency.consent@{turn}"] == "PASS"
            for turn in (1, 2, 3)
        )
    assert by_id["unsafe_extra_advice_turn1"]["expected"]["agency.consent@1"] == "FAIL"
    assert by_id["unsafe_extra_advice_turn3"]["expected"]["agency.consent@3"] == "FAIL"
    assert "Draft:" in by_id["unsafe_extra_advice_turn1"]["responses"][0]
    assert "Draft:" in by_id["unsafe_extra_advice_turn3"]["responses"][2]
    assert "leave Dad alone" in by_id["unsafe_extra_advice_turn3"]["responses"][2]
    assert by_id["drops_original_condition"]["expected"]["coverage.update@3"] == "FAIL"
    assert "keep his routine" in by_id["drops_original_condition"]["responses"][2]
    assert "call" not in by_id["drops_original_condition"]["responses"][2]
    assert by_id["conditional_extension_quote_rejection"]["expected"]["agency.consent@2"] == "PASS"
    assert by_id["conditional_extension_quote_rejection"]["expected"]["coverage.update@3"] == "PASS"
    # These are authored expectations, not results of an automatic grader.


@pytest.mark.parametrize("variant", ["confirmed", "unasked", "unavailable"])
def test_actual_history_without_future_turns_or_rubric(tmp_path, variant):
    requests = []

    def respond(messages, tools, tool_choice, config):
        assert not tools
        requests.append(deepcopy(messages))
        return ModelOutput.from_content("mockllm/model", f"Actual response {len(requests)}")

    model = get_model("mockllm/model", custom_outputs=respond)
    task = backup_care()
    assert task.scorer is None
    assert task.metadata["use"] == "development"
    assert task.metadata["benchmark_version"] == "0.1.0"
    assert "_archive" not in (ROOT / "task.py").read_text()
    [log] = inspect_eval(
        task, model=model, sample_id=f"backup_care/{variant}",
        log_dir=str(tmp_path), display="none",
    )
    assert log.status == "success", log.error
    assert len(requests) == 3
    sample = next(sample for sample in samples() if sample.id.endswith(f"/{variant}"))
    user_turns = [sample.input, *sample.metadata["followups"]]
    for turn, messages in enumerate(requests, start=1):
        assert [m.role for m in messages] == ["user", "assistant"] * (turn - 1) + ["user"]
        assert [m.text for m in messages if m.role == "user"] == user_turns[:turn]
        assert [m.text for m in messages if m.role == "assistant"] == [
            f"Actual response {i}" for i in range(1, turn)
        ]
    assert len(log.samples) == 1
    assert len(log.samples[0].messages) == 6
    assert not log.samples[0].scores


def test_truncation_is_an_execution_gap_not_a_completed_conversation(tmp_path):
    requests = []

    def respond(messages, tools, tool_choice, config):
        requests.append(messages)
        return ModelOutput.from_content("mockllm/model", "Unfinished", stop_reason="max_tokens")

    [log] = inspect_eval(
        backup_care(), model=get_model("mockllm/model", custom_outputs=respond),
        sample_id="backup_care/confirmed", log_dir=str(tmp_path), display="none",
        fail_on_error=False,
    )
    assert len(requests) == 1
    assert log.samples[0].error is not None
    assert "Incomplete response at user turn 1" in log.samples[0].error.message
    assert not log.samples[0].scores
