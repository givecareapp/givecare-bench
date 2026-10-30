import hashlib
import importlib
import json
import sys
from copy import deepcopy

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.log import read_eval_log
from inspect_ai.model import (
    ModelCost,
    ModelInfo,
    ModelOutput,
    get_model,
    get_model_info,
    set_model_info,
)

from task import OPENROUTER_PRICES, ROOT, conversation_family, load_case, opening, samples

# Every directory under cases/ is a family; new families are covered without listing them.
FAMILIES = sorted(p.parent.name for p in (ROOT / "cases").glob("*/case.json"))

# The models whose list prices task.py must register so Inspect can record their cost.
PRICED = [
    "openrouter/anthropic/claude-haiku-5.5",
    "openrouter/openai/gpt-5.6-luna-pro",
    "openrouter/openai/gpt-5.6-luna",
    "openrouter/google/gemini-3.1-flash-lite",
    "openrouter/deepseek/deepseek-v4.1-flash",
    "openrouter/meta-llama/llama-3.3-70b-instruct",
]


def _field(variant):
    [field] = set(variant) - {"id"}
    return field


@pytest.mark.parametrize("name", FAMILIES)
def test_family_contract(name):
    family = load_case(name)
    directory = ROOT / "cases" / name
    dataset = samples(name)
    field = _field(family["variants"][0])
    assert all(_field(v) == field for v in family["variants"])
    assert family["opening"].count("{" + field + "}") == 1
    assert len(dataset) == len(family["variants"]) == 3
    assert len({sample.id for sample in dataset}) == 3
    assert [str(sample.id) for sample in dataset] == [
        f"{name}/{v['id']}" for v in family["variants"]
    ]
    assert len(family["followups"]) == 2
    for sample, variant in zip(dataset, family["variants"], strict=True):
        assert sample.input == opening(family, variant)
        assert sample.input.replace(variant[field], "{" + field + "}") == family["opening"]
        assert sample.target == ""
        assert sample.metadata == {"followups": family["followups"]}
    rubric = json.loads((directory / "rubric.json").read_text())
    controls = [json.loads(line) for line in (directory / "controls.jsonl").read_text().splitlines()]
    opportunities = {
        f"{check['id']}@{turn}"
        for check in rubric["checks"]
        for turn in check["turns"]
    }
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


def test_unknown_family_is_rejected():
    for name in ("no_such_family", "..", "../cases/backup_care", ""):
        with pytest.raises(ValueError, match="Unknown family"):
            conversation_family(name)
        with pytest.raises(ValueError, match="Unknown family"):
            samples(name)


def test_task_metadata_names_its_own_family():
    for name in FAMILIES:
        task = conversation_family(name)
        assert task.metadata["family"] == name
        digest = hashlib.sha256((ROOT / "cases" / name / "case.json").read_bytes()).hexdigest()
        assert task.metadata["case_sha256"] == digest
    assert conversation_family().metadata["family"] == "backup_care"
    assert (conversation_family("backup_care").metadata["case_sha256"]
            != conversation_family("fluctuating_capacity").metadata["case_sha256"])


def test_backup_care_content_and_control_bindings():
    family = load_case("backup_care")
    dataset = samples("backup_care")
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
    rubric = json.loads((ROOT / "cases/backup_care/rubric.json").read_text())
    controls = [
        json.loads(line)
        for line in (ROOT / "cases/backup_care/controls.jsonl").read_text().splitlines()
    ]
    assert len({f"{c['id']}@{t}" for c in rubric["checks"] for t in c["turns"]}) == 14
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
    task = conversation_family("backup_care")
    assert task.scorer is None
    assert task.metadata["use"] == "development"
    assert task.metadata["benchmark_version"] == "0.1.4"
    assert "_archive" not in (ROOT / "task.py").read_text()
    [log] = inspect_eval(
        task, model=model, sample_id=f"backup_care/{variant}",
        log_dir=str(tmp_path), display="none",
    )
    assert log.status == "success", log.error
    assert len(requests) == 3
    sample = next(sample for sample in samples("backup_care") if sample.id.endswith(f"/{variant}"))
    user_turns = [sample.input, *sample.metadata["followups"]]
    for turn, messages in enumerate(requests, start=1):
        assert [m.role for m in messages] == ["user", "assistant"] * (turn - 1) + ["user"]
        assert [m.text for m in messages if m.role == "user"] == user_turns[:turn]
        assert [m.text for m in messages if m.role == "assistant"] == [
            f"Actual response {i}" for i in range(1, turn)
        ]
    assert len(log.samples) == 1
    assert len(log.samples[0].messages) == 6
    assert log.samples[0].metadata["completed_turns"] == 3
    assert not log.samples[0].scores


def test_truncation_is_an_execution_gap_not_a_completed_conversation(tmp_path):
    requests = []

    def respond(messages, tools, tool_choice, config):
        requests.append(messages)
        return ModelOutput.from_content("mockllm/model", "Unfinished", stop_reason="max_tokens")

    [log] = inspect_eval(
        conversation_family("backup_care"), model=get_model("mockllm/model", custom_outputs=respond),
        sample_id="backup_care/confirmed", log_dir=str(tmp_path), display="none",
        fail_on_error=False,
    )
    assert len(requests) == 1
    assert log.samples[0].error is not None
    assert "Incomplete response at user turn 1" in log.samples[0].error.message
    assert log.samples[0].metadata["completed_turns"] == 0
    assert not log.samples[0].scores


@pytest.mark.parametrize("name", [f for f in FAMILIES if f.endswith("_implicit")])
def test_implicit_twin_shares_parent_labels(name):
    # A twin removes only the cue, so every parent control and label applies to it unchanged.
    # The twin may add controls of its own; it may not relabel a parent control.
    parent = name.removesuffix("_implicit")
    assert parent in FAMILIES

    def labels(family):
        rows = [json.loads(line) for line in (ROOT / "cases" / family / "controls.jsonl").read_text().splitlines()]
        return {row["id"]: row["expected"] for row in rows}

    parent_labels, twin_labels = labels(parent), labels(name)
    assert set(parent_labels) <= set(twin_labels)
    for control_id, expected in parent_labels.items():
        assert twin_labels[control_id] == expected, control_id


@pytest.mark.parametrize("name", PRICED)
def test_registered_price_matches_the_table(name):
    input_price, output_price, cache_read_price = OPENROUTER_PRICES[name]
    assert get_model_info(name).cost == ModelCost(
        input=input_price,
        output=output_price,
        input_cache_write=input_price,
        input_cache_read=cache_read_price,
    )


def test_importing_task_again_changes_no_price():
    def registered():
        return {name: get_model_info(name).model_dump() for name in PRICED}

    before = registered()
    importlib.reload(sys.modules["task"])
    assert registered() == before


def test_unlisted_model_is_not_priced():
    info = get_model_info("openrouter/example")
    assert info is None or info.cost is None


def test_registered_price_becomes_recorded_cost(tmp_path):
    # Inspect has no call to unregister one model. A name no other test uses keeps this
    # price out of every run that uses mockllm/model.
    set_model_info(
        "mockllm/priced",
        ModelInfo(cost=ModelCost(input=1.0, output=2.0, input_cache_write=1.0, input_cache_read=0.1)),
    )
    [log] = inspect_eval(
        conversation_family("backup_care"), model="mockllm/priced",
        sample_id="backup_care/confirmed", log_dir=str(tmp_path), display="none",
    )
    assert log.status == "success", log.error
    saved = read_eval_log(log.location, header_only=True)
    usage = saved.stats.model_usage["mockllm/priced"]
    assert usage.input_tokens > 0 and usage.output_tokens > 0
    assert usage.total_cost is not None
    assert usage.total_cost == pytest.approx(
        (usage.input_tokens * 1.0 + usage.output_tokens * 2.0) / 1_000_000
    )
