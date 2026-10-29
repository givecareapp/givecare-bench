import asyncio
import json
from collections import Counter
from copy import deepcopy
from glob import glob
from types import SimpleNamespace

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, get_model

from grader import (
    bounded_judge,
    control_judge,
    control_samples,
    parse_judgment,
    summarize,
    target_judge,
)
from report import build_report
from task import CASE, backup_care


def _transcript(turn=3):
    transcript = []
    for n in range(1, turn + 1):
        transcript.append({"role": "user", "turn": n, "content": f"User cue {n}."})
        transcript.append({"role": "assistant", "turn": n, "content": f"Assistant reply {n}."})
    return transcript


def _judgment(**overrides):
    value = {
        "verdict": "PASS",
        "reason": "The response follows the stated requirement.",
        "response_quote": "Assistant reply 3.",
        "cue_turn": 3,
        "cue_quote": "User cue 3.",
    }
    value.update(overrides)
    return json.dumps(value)


def test_parse_judgment_accepts_only_grounded_exact_shape():
    transcript = _transcript()
    assert parse_judgment(_judgment(), transcript) == {
        "verdict": "PASS",
        "reason": "The response follows the stated requirement.",
        "response_quote": "Assistant reply 3.",
        "cue_turn": 3,
        "cue_quote": "User cue 3.",
    }


@pytest.mark.parametrize(
    "raw, transcript, message",
    [
        ("not json", _transcript(), None),
        ('{"verdict":"PASS","verdict":"FAIL"}', _transcript(), None),
        (_judgment(extra="field"), _transcript(), None),
        (_judgment(cue_turn="3"), _transcript(), "cue_turn"),
        (_judgment(cue_turn=True), _transcript(), "cue_turn"),
        (_judgment(verdict="MAYBE"), _transcript(), "verdict"),
        (_judgment(verdict=[]), _transcript(), "verdict"),
        (_judgment(reason="  "), _transcript(), "reason"),
        (_judgment(response_quote="not in transcript"), _transcript(), "response_quote"),
        (_judgment(cue_quote="not in transcript"), _transcript(), "cue_quote"),
        (_judgment(cue_turn=4, cue_quote="User cue 4."), _transcript(), None),
        (_judgment(response_quote="Assistant reply 1.", cue_turn=2,
                   cue_quote="User cue 2."), _transcript(1), None),
    ],
)
def test_parse_judgment_rejects_invalid_or_unverifiable_evidence(raw, transcript, message):
    error = pytest.raises(ValueError) if message is None else pytest.raises(ValueError, match=message)
    with error:
        parse_judgment(raw, transcript)


def test_control_samples_bind_each_control_to_one_prefix_only_check():
    samples = control_samples()
    rubric = json.loads((CASE.parent / "rubric.json").read_text())
    controls = [
        json.loads(line)
        for line in (CASE.parent / "controls.jsonl").read_text().splitlines()
    ]
    planned = {
        f"{control['id']}/{check['id']}@{turn}": (control, check, turn)
        for control in controls
        for check in rubric["checks"]
        for turn in check["turns"]
    }
    assert len(samples) == len(planned) == 238
    assert len({sample.id for sample in samples}) == len(samples)
    for sample in samples:
        control, check, turn = planned[sample.id]
        assert sample.target == control["expected"][f"{check['id']}@{turn}"]
        assert sample.metadata == {"check": check["id"], "layer": check["layer"], "turn": turn}
        assert len(sample.input) == 2
        prompt = json.loads(sample.input[1].text)
        # The actual serialized prompt contains only the criterion and observed prefix.
        assert set(prompt) == {"criterion", "response_turn", "conversation"}
        assert prompt["criterion"] == check
        assert prompt["response_turn"] == turn
        conversation = prompt["conversation"]
        family = json.loads(CASE.read_text())
        variant = next(v for v in family["variants"] if v["id"] == control["variant"])
        users = [
            family["opening"].replace("{availability}", variant["availability"]),
            *family["followups"],
        ]
        assert [entry["role"] for entry in conversation] == [
            role for _ in range(turn) for role in ("user", "assistant")
        ]
        assert [entry["turn"] for entry in conversation] == [
            n for n in range(1, turn + 1) for _ in (0, 1)
        ]
        assert conversation[-1] == {
            "role": "assistant",
            "turn": turn,
            "content": control["responses"][turn - 1],
        }
        assert [entry["content"] for entry in conversation if entry["role"] == "user"] == users[:turn]
        assert [entry["content"] for entry in conversation if entry["role"] == "assistant"] == control["responses"][:turn]
        assert all(
            entry["content"] != control.get("rationale")
            and control["id"] not in entry["content"]
            for entry in conversation
        )


def test_target_judge_uses_saved_generation_without_control_labels(tmp_path):
    generation_dir = tmp_path / "generation"
    [generation] = inspect_eval(
        backup_care(), model="mockllm/model", sample_id="backup_care/confirmed",
        log_dir=str(generation_dir), display="none",
    )
    assert generation.status == "success"
    task = target_judge(glob(str(generation_dir / "*.eval"))[0])
    assert task.metadata["use"] == "target-judging"
    assert len(task.dataset) == 14
    assert task.metadata["source"]["complete_samples"] == 1
    assert task.metadata["source"]["benchmark_version"] == task.metadata["benchmark_version"]
    assert task.metadata["source"]["settings"]["config"]
    assert task.metadata["source"]["settings"]["plan"]["config"]["max_tokens"] == 2048
    assert task.metadata["source"]["runner_sha256"] == generation.eval.metadata["runner_sha256"]
    assert not any(sample.target for sample in task.dataset)
    for sample in task.dataset:
        prompt = json.loads(sample.input[-1].text)
        assert set(prompt) == {"criterion", "response_turn", "conversation"}
        assert "expected" not in sample.input[-1].text

    [judged] = inspect_eval(
        task, model="mockllm/model", sample_id=str(task.dataset[0].id),
        log_dir=str(tmp_path / "judged"), display="none", fail_on_error=False,
    )
    report = build_report(judged)
    counts = report["summary"]["by_layer"][task.dataset[0].metadata["layer"]][
        task.dataset[0].metadata["check"]]
    assert counts["recorded"] == counts["unscored"] == 1
    assert counts["missing"] == counts["planned"] - 1
    assert counts["generation_missing"] == 2
    assert counts["judge_missing"] == 0
    other = report["summary"]["by_layer"]["Care"]["task.message"]
    assert other["planned"] == other["generation_missing"] + other["judge_missing"] == 6
    assert report["summary"]["target"]["source_log_sha256"]
    assert report["trials"][0]["source_sample"] == "backup_care/confirmed"
    assert report["run"]["versions"] is not None
    assert report["run"]["benchmark_version"] == task.metadata["benchmark_version"]
    assert report["trials"][0]["unscored_reason"]

    def valid_judgment(messages, tools, tool_choice, config):
        assert not tools
        prompt = json.loads(messages[-1].text)
        conversation = prompt["conversation"]
        assert "expected" not in messages[-1].text
        return ModelOutput.from_content("mockllm/model", _judgment(
            response_quote=conversation[-1]["content"],
            cue_turn=prompt["response_turn"], cue_quote=conversation[-2]["content"],
        ))

    [valid_log] = inspect_eval(
        task, model=get_model("mockllm/model", custom_outputs=valid_judgment),
        sample_id=str(task.dataset[0].id), log_dir=str(tmp_path / "valid"),
        display="none", fail_on_error=False,
    )
    valid_report = build_report(valid_log)
    valid_counts = valid_report["summary"]["by_layer"][task.dataset[0].metadata["layer"]][
        task.dataset[0].metadata["check"]]
    assert valid_counts["PASS"] == 1
    assert valid_counts["unscored"] == 0
    assert valid_report["trials"][0]["evidence"]["response_quote"]


@pytest.mark.parametrize("prediction", ["PASS", "FAIL"])
def test_fixed_verdict_mock_exposes_errors_without_claiming_accuracy(tmp_path, prediction):
    requests = []

    def respond(messages, tools, tool_choice, config):
        assert not tools
        requests.append(deepcopy(messages))
        prompt = json.loads(messages[-1].text)
        turn = prompt["response_turn"]
        current_response = next(
            entry["content"]
            for entry in reversed(prompt["conversation"])
            if entry["role"] == "assistant" and entry["turn"] == turn
        )
        cue = next(
            entry["content"]
            for entry in reversed(prompt["conversation"])
            if entry["role"] == "user" and entry["turn"] == turn
        )
        return ModelOutput.from_content(
            "mockllm/model",
            _judgment(verdict=prediction, response_quote=current_response, cue_quote=cue, cue_turn=turn),
        )

    task = control_judge()
    assert task.metadata["use"] == "judge-development"
    [log] = inspect_eval(
        task,
        model=get_model("mockllm/model", custom_outputs=respond),
        log_dir=str(tmp_path),
        display="none",
        fail_on_error=False,
    )
    assert log.status == "success", log.error
    assert len(requests) == 238
    report = summarize(log)
    audit = build_report(log)
    assert audit["summary"] == report
    assert len(audit["trials"]) == 238
    assert audit["run"]["model"] == "mockllm/model"
    assert audit["summary"]["source_sha256"] == task.metadata["source_sha256"]
    assert all(trial["verdict"] == prediction and trial["evidence"] for trial in audit["trials"])
    assert report["status"] == "success"
    assert report["basis"] == "authored controls; no independent validation"
    totals = Counter()
    for layer in ("Safety", "Care"):
        for counts in report["by_layer"][layer].values():
            totals.update({key: value for key, value in counts.items() if isinstance(value, int)})
    assert totals["planned"] == totals["recorded"] == 238
    assert totals["missing"] == totals["unscored"] == totals["execution_error"] == 0
    # The fake always returns one verdict: the report must expose its errors and
    # must not call the result grader accuracy or model quality.
    expected_counts = Counter(sample.target for sample in task.dataset)
    assert totals["exact_match"] == expected_counts[prediction]
    assert totals["false_pass"] == (expected_counts["FAIL"] if prediction == "PASS" else 0)
    assert totals["false_fail"] == (expected_counts["PASS"] if prediction == "FAIL" else 0)
    assert totals["applicability_error"] == expected_counts["NOT_APPLICABLE"]
    assert "accuracy" not in json.dumps(report).lower()
    assert "rank" not in json.dumps(report).lower()
    broken = log.model_copy(deep=True)
    broken.samples[0].target = "UNCLEAR"
    with pytest.raises(ValueError, match="frozen reference"):
        summarize(broken)


def test_limited_two_epoch_log_preserves_categories_and_reports_missing(tmp_path):
    requests = []

    def respond(messages, tools, tool_choice, config):
        assert not tools
        requests.append(deepcopy(messages))
        prompt = json.loads(messages[-1].text)
        turn = prompt["response_turn"]
        response = next(
            entry["content"] for entry in prompt["conversation"]
            if entry["role"] == "assistant" and entry["turn"] == turn
        )
        cue = next(
            entry["content"] for entry in prompt["conversation"]
            if entry["role"] == "user" and entry["turn"] == turn
        )
        verdict = "UNCLEAR" if prompt["criterion"]["id"] == "care.alternative" else "NOT_APPLICABLE"
        return ModelOutput.from_content(
            "mockllm/model",
            _judgment(verdict=verdict, response_quote=response, cue_quote=cue, cue_turn=turn),
        )

    ids = [
        "supported_confirmed/care.alternative@2",
        "supported_confirmed/privacy.message@2",
    ]
    [log] = inspect_eval(
        control_judge(),
        model=get_model("mockllm/model", custom_outputs=respond),
        sample_id=ids,
        epochs=2,
        log_dir=str(tmp_path),
        display="none",
        fail_on_error=False,
    )
    assert log.status == "success", log.error
    assert len(requests) == len(log.samples) == 4
    assert Counter(str(sample.id) for sample in log.samples) == Counter({sample_id: 2 for sample_id in ids})
    assert {sample.epoch for sample in log.samples} == {1, 2}

    report = summarize(log)
    care = report["by_layer"]["Care"]["care.alternative"]
    assert care["planned"] == 2 * 17
    assert care["recorded"] == care["unclear"] == 2
    assert care["missing"] == care["planned"] - care["recorded"]
    assert care["confusion"]["PASS"]["UNCLEAR"] == 2
    safety = report["by_layer"]["Safety"]["privacy.message"]
    assert safety["planned"] == 2 * 17 * 3
    assert safety["recorded"] == 2
    assert safety["missing"] == safety["planned"] - safety["recorded"]
    assert safety["applicability_error"] == 2
    assert safety["confusion"]["PASS"]["NOT_APPLICABLE"] == 2


@pytest.mark.parametrize("stop_reason, completion", [
    ("max_tokens", ""), ("stop", "not JSON"),
])
def test_invalid_judge_output_is_unscored_not_a_false_pass(tmp_path, stop_reason, completion):
    def respond(messages, tools, tool_choice, config):
        return ModelOutput.from_content("mockllm/model", completion, stop_reason=stop_reason)

    [log] = inspect_eval(
        control_judge(),
        model=get_model("mockllm/model", custom_outputs=respond),
        sample_id="supported_confirmed/coverage.status@1",
        log_dir=str(tmp_path),
        display="none",
        fail_on_error=False,
    )
    assert log.status == "success", log.error
    report = summarize(log)
    audit = build_report(log)
    assert audit["trials"][0]["verdict"] is None
    assert audit["trials"][0]["unscored_reason"]
    coverage = report["by_layer"]["Care"]["coverage.status"]
    assert coverage["recorded"] == 1
    assert coverage["unscored"] == 1
    assert coverage["execution_error"] == 0
    assert coverage["missing"] == coverage["planned"] - 1
    assert coverage["false_pass"] == coverage["exact_match"] == 0


def test_execution_failure_remains_distinct_from_a_judge_answer(tmp_path):
    def respond(messages, tools, tool_choice, config):
        raise RuntimeError("Deliberate offline provider failure")

    [log] = inspect_eval(
        control_judge(),
        model=get_model("mockllm/model", custom_outputs=respond),
        sample_id="supported_confirmed/coverage.status@1",
        log_dir=str(tmp_path), display="none", fail_on_error=False,
    )
    assert log.samples[0].error.message == "RuntimeError('Deliberate offline provider failure')"
    coverage = summarize(log)["by_layer"]["Care"]["coverage.status"]
    assert coverage["recorded"] == coverage["execution_error"] == 1
    assert coverage["unscored"] == coverage["false_pass"] == coverage["exact_match"] == 0
    assert coverage["missing"] == coverage["planned"] - 1


@pytest.mark.parametrize("amount", [0, -1, float("nan"), float("inf"), True])
def test_invalid_cost_limits_are_rejected(amount):
    with pytest.raises(ValueError, match="finite positive"):
        control_judge(amount)


@pytest.mark.parametrize("model", ["openrouter/example", "openai/example"])
def test_live_guard_prevents_dispatch_without_supported_provider_and_ceiling(model):
    async def forbidden_generate(state):
        pytest.fail("Live request must not be dispatched")

    with pytest.raises(ValueError, match="requires"):
        asyncio.run(bounded_judge()(SimpleNamespace(model=model), forbidden_generate))
