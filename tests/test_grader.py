import asyncio
import hashlib
import json
import subprocess
from collections import Counter
from copy import deepcopy
from glob import glob
from types import SimpleNamespace

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.log import read_eval_log, write_eval_log
from inspect_ai.model import ModelOutput, get_model

from grader import (
    VERDICTS,
    bounded_judge,
    control_judge,
    control_samples,
    parse_judgment,
    summarize,
    summarize_target,
    target_judge,
)
from report import build_report, render_markdown
from review_packet import build_packet
from task import ROOT, conversation_family, load_case, opening

# Every directory under cases/ is a family; new families are covered without listing them.
FAMILIES = sorted(p.parent.name for p in (ROOT / "cases").glob("*/case.json"))


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


def _record_git_revision(monkeypatch):
    # Inspect skips git while pytest runs, so a mock log has no native revision. Call this
    # inside the test body: pytest sets the variable again at the start of each phase.
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)


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


@pytest.mark.parametrize("name", FAMILIES)
def test_control_samples_bind_each_control_to_one_prefix_only_check(name):
    samples = control_samples(name)
    rubric = json.loads((ROOT / "cases" / name / "rubric.json").read_text())
    controls = [
        json.loads(line)
        for line in (ROOT / "cases" / name / "controls.jsonl").read_text().splitlines()
    ]
    planned = {
        f"{control['id']}/{check['id']}@{turn}": (control, check, turn)
        for control in controls
        for check in rubric["checks"]
        for turn in check["turns"]
    }
    assert len(samples) == len(planned)
    if name == "backup_care":
        assert len(samples) == 238
    assert len({sample.id for sample in samples}) == len(samples)
    for sample in samples:
        control, check, turn = planned[sample.id]
        assert sample.target == control["expected"][f"{check['id']}@{turn}"]
        assert sample.metadata == {"check": check["id"], "layer": check["layer"], "turn": turn}
        assert len(sample.input) == 2
        assert "expected" not in sample.input[1].text
        prompt = json.loads(sample.input[1].text)
        # The actual serialized prompt contains only the criterion and observed prefix.
        assert set(prompt) == {"criterion", "response_turn", "conversation"}
        assert prompt["criterion"] == check
        assert prompt["response_turn"] == turn
        conversation = prompt["conversation"]
        family = load_case(name)
        variant = next(v for v in family["variants"] if v["id"] == control["variant"])
        users = [opening(family, variant), *family["followups"]]
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
        conversation_family("backup_care"), model="mockllm/model",
        sample_id="backup_care/confirmed",
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
    packet = build_packet(glob(str(generation_dir / "*.eval"))[0])
    assert len(packet["items"]) == 14
    assert packet["complete_conversations"] == 1
    assert packet["planned_conversations"] == 3
    assert packet["source_log_sha256"] == task.metadata["source"]["source_log_sha256"]
    assert packet["rubric_sha256"] == task.metadata["source_sha256"]["rubric.json"]
    assert "model" not in packet and "verdict" not in json.dumps(packet)
    assert all(set(item) == {"item_id", "family_id", "criterion", "response_turn", "conversation"}
               for item in packet["items"])
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
    assert counts["generation_missing"] == counts["generation_unattempted"] == 2
    assert counts["generation_interrupted"] == 0
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
    readable = render_markdown(valid_report)
    assert "# InvisibleBench evaluation report" in readable
    assert "| 1 | 0 | 0 | 0 |" in readable
    assert "Source generation" in readable
    assert valid_report["summary"]["target"]["source_log_sha256"] in readable


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
    # The readable report must show the same disagreements the JSON holds.
    readable = render_markdown(audit)
    first = next(iter(report["by_layer"]["Safety"].values()))
    ref = first["reference_counts"]
    expected_row = (
        f"| {first['planned']} | {ref.get('PASS', 0)} | {ref.get('FAIL', 0)} | "
        f"{ref.get('UNCLEAR', 0)} | {ref.get('NOT_APPLICABLE', 0)} | {first['exact_match']} | "
        f"{first['false_pass']} | {first['false_fail']} | {first['applicability_error']} | "
        f"{first['unclear']} | 0 | 0 | 0 |"
    )
    assert expected_row in readable
    assert "Control counts compare judge output" in readable
    assert "## Judge disagreements requiring review" in readable
    assert "Response evidence:" in readable
    assert "No recorded FAIL" not in readable
    if prediction == "PASS":
        assert readable.count("### False pass:") == totals["false_pass"] == 34
        assert "FAIL→PASS" in readable
    else:
        assert readable.count("### False fail:") == totals["false_fail"]
        assert "PASS→FAIL" in readable
    assert readable.count("### Applicability disagreement:") == totals["applicability_error"]
    assert "rank" not in readable.lower()
    broken = log.model_copy(deep=True)
    broken.samples[0].target = "UNCLEAR"
    with pytest.raises(ValueError, match="frozen reference"):
        summarize(broken)


def test_interrupted_generation_keeps_completed_turns_and_its_error(tmp_path):
    def respond(messages, tools, tool_choice, config):
        opening = messages[0].text
        turn = sum(m.role == "user" for m in messages)
        if "cannot stay" in opening and turn == 3:
            raise RuntimeError("Deliberate provider outage at turn 3")
        if "has not been asked" in opening and turn == 2:
            return ModelOutput.from_content("mockllm/model", "Unfinished draft", stop_reason="max_tokens")
        return ModelOutput.from_content("mockllm/model", f"Complete reply {turn}.")

    generation_dir = tmp_path / "generation"
    [generation] = inspect_eval(
        conversation_family("backup_care"), model=get_model("mockllm/model", custom_outputs=respond),
        log_dir=str(generation_dir), display="none", fail_on_error=False,
    )
    by_id = {str(sample.id): sample for sample in generation.samples}
    assert by_id["backup_care/confirmed"].error is None
    assert by_id["backup_care/unasked"].metadata["completed_turns"] == 1
    assert by_id["backup_care/unavailable"].metadata["completed_turns"] == 2
    assert "Unfinished draft" in by_id["backup_care/unasked"].messages[-1].text

    source_log = glob(str(generation_dir / "*.eval"))[0]
    task = target_judge(source_log)
    # confirmed: 14 opportunities; unasked: turn 1 only (5); unavailable: turns 1-2 (9).
    assert len(task.dataset) == 14 + 5 + 9
    assert "Unfinished draft" not in json.dumps([s.input[-1].text for s in task.dataset])
    source = task.metadata["source"]
    assert source["planned_samples"] == 3
    assert source["complete_samples"] == 1 and source["interrupted_samples"] == 2
    assert {(c["sample_id"], c["status"], c["completed_turns"]) for c in source["conversations"]} == {
        ("backup_care/confirmed", "complete", 3),
        ("backup_care/unasked", "interrupted", 1),
        ("backup_care/unavailable", "interrupted", 2),
    }
    errors = {c["sample_id"]: c["error"] for c in source["conversations"] if c["error"]}
    assert "Deliberate provider outage at turn 3" in errors["backup_care/unavailable"]
    assert "Incomplete response at user turn 2" in errors["backup_care/unasked"]
    assert len(build_packet(source_log)["items"]) == 28

    def valid_judgment(messages, tools, tool_choice, config):
        prompt = json.loads(messages[-1].text)
        conversation = prompt["conversation"]
        return ModelOutput.from_content("mockllm/model", _judgment(
            response_quote=conversation[-1]["content"],
            cue_turn=prompt["response_turn"], cue_quote=conversation[-2]["content"],
        ))

    [judged] = inspect_eval(
        task, model=get_model("mockllm/model", custom_outputs=valid_judgment),
        log_dir=str(tmp_path / "judged"), display="none", fail_on_error=False,
    )
    report = build_report(judged)
    consent = report["summary"]["by_layer"]["Safety"]["agency.consent"]
    assert consent["planned"] == 9 and consent["recorded"] == consent["PASS"] == 6
    assert consent["missing"] == consent["generation_interrupted"] == 3
    assert consent["generation_unattempted"] == consent["judge_missing"] == 0
    assert consent["execution_error"] == consent["unscored"] == 0
    update = report["summary"]["by_layer"]["Care"]["coverage.update"]
    assert update["planned"] == 3 and update["recorded"] == 1
    assert update["generation_interrupted"] == 2
    readable = render_markdown(report)
    assert "| Interrupted | Unattempted |" in readable
    assert "1 complete, 2 interrupted, of 3 planned" in readable
    assert "`backup_care/unavailable` (epoch 1): interrupted, 2 of 3 turns completed" in readable
    assert "Deliberate provider outage at turn 3" in readable
    assert "`backup_care/unasked` (epoch 1): interrupted, 1 of 3 turns completed" in readable
    assert "Unfinished draft" not in readable


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


def test_fluctuating_capacity_round_trips_through_judging_and_report(tmp_path):
    generation_dir = tmp_path / "generation"
    [generation] = inspect_eval(
        conversation_family("fluctuating_capacity"), model="mockllm/model",
        log_dir=str(generation_dir), display="none",
    )
    assert generation.status == "success"
    assert generation.eval.metadata["family"] == "fluctuating_capacity"
    source_log = glob(str(generation_dir / "*.eval"))[0]
    task = target_judge(source_log)
    rubric = json.loads((ROOT / "cases/fluctuating_capacity/rubric.json").read_text())
    per_variant = sum(len(check["turns"]) for check in rubric["checks"])
    assert len(task.dataset) == 3 * per_variant
    assert task.metadata["family"] == task.metadata["source"]["family"] == "fluctuating_capacity"
    assert all(str(s.id).startswith("fluctuating_capacity/") for s in task.dataset)
    assert task.metadata["source_sha256"]["rubric.json"] == hashlib.sha256(
        (ROOT / "cases/fluctuating_capacity/rubric.json").read_bytes()).hexdigest()
    assert task.metadata["source_sha256"]["case.json"] == generation.eval.metadata["case_sha256"]
    packet = build_packet(source_log)
    assert packet["family"] == "fluctuating_capacity"
    assert packet["rubric_sha256"] == task.metadata["source_sha256"]["rubric.json"]
    assert {item["family_id"] for item in packet["items"]} == {"fluctuating_capacity"}
    for sample in task.dataset:
        prompt = json.loads(sample.input[-1].text)
        assert set(prompt) == {"criterion", "response_turn", "conversation"}
        assert "expected" not in sample.input[-1].text

    [judged] = inspect_eval(
        task, model="mockllm/model", sample_id=str(task.dataset[0].id),
        log_dir=str(tmp_path / "judged"), display="none", fail_on_error=False,
    )
    report = build_report(judged)
    assert report["run"]["family"] == report["summary"]["family"] == "fluctuating_capacity"
    assert summarize_target(judged)["family"] == "fluctuating_capacity"
    assert "**Family:** fluctuating_capacity" in render_markdown(report)


def test_control_judge_reads_the_named_family():
    task = control_judge(family="fluctuating_capacity")
    assert task.metadata["family"] == "fluctuating_capacity"
    assert set(task.metadata["source_sha256"]) == {
        "case.json", "rubric.json", "controls.jsonl", "pyproject.toml", "grader.py"}
    assert task.metadata["source_sha256"]["controls.jsonl"] == hashlib.sha256(
        (ROOT / "cases/fluctuating_capacity/controls.jsonl").read_bytes()).hexdigest()
    assert all(str(s.id).split("/")[1].count("@") == 1 for s in task.dataset)
    with pytest.raises(ValueError, match="Unknown family"):
        control_judge(family="no_such_family")


def test_target_judge_refuses_unknown_family_and_changed_case(tmp_path):
    generation_dir = tmp_path / "generation"
    inspect_eval(
        conversation_family("fluctuating_capacity"), model="mockllm/model",
        sample_id="fluctuating_capacity/settled", log_dir=str(generation_dir), display="none",
    )
    source_log = glob(str(generation_dir / "*.eval"))[0]
    log = read_eval_log(source_log)
    for field, value, message in (
        ("family", "no_such_family", "Unknown family"),
        ("family", "backup_care", "differs from the current case"),
    ):
        log.eval.metadata[field] = value
        forged = tmp_path / f"forged-{value}.eval"
        write_eval_log(log, str(forged))
        with pytest.raises(ValueError, match=message):
            target_judge(str(forged))


def test_judge_tasks_bind_to_committed_case_files(tmp_path, monkeypatch):
    # A judge run records the commit it ran at and refuses uncommitted case files,
    # so a saved verdict can always be traced to the rubric and labels git holds.
    task = control_judge()
    # Inspect records the commit in the log; the task keeps only the uncommitted files.
    assert "git_commit" not in task.metadata
    # Code edits in progress are recorded, never a reason to refuse; case files are.
    assert not [p for p in task.metadata["uncommitted"] if p.startswith("cases/")]
    rubric = ROOT / "cases/backup_care/rubric.json"
    original = rubric.read_bytes()
    try:
        rubric.write_bytes(original + b"\n")
        with pytest.raises(ValueError, match="Commit before judging.*cases/backup_care/rubric.json"):
            control_judge()
    finally:
        rubric.write_bytes(original)
    assert not [p for p in control_judge().metadata["uncommitted"] if p.startswith("cases/")]

    _record_git_revision(monkeypatch)
    [log] = inspect_eval(
        task, model="mockllm/model", sample_id=str(task.dataset[0].id),
        log_dir=str(tmp_path), display="none", fail_on_error=False,
    )
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    native = log.eval.revision
    assert native.commit == head and isinstance(native.dirty, bool)
    revision = {"origin": native.origin, "commit": head, "dirty": native.dirty}
    audit = build_report(log)
    assert audit["summary"]["revision"] == audit["run"]["revision"] == revision
    assert f"**Revision:** commit {head}, dirty {native.dirty}" in render_markdown(audit)
    # A log that recorded no revision still reports, with every field None.
    unrecorded = log.model_copy(deep=True)
    unrecorded.eval.revision = None
    audit = build_report(unrecorded)
    assert audit["summary"]["revision"] == audit["run"]["revision"] == {
        "origin": None, "commit": None, "dirty": None}
    assert "**Revision:** none recorded" in render_markdown(audit)


def test_report_diff_pairs_samples_and_lists_every_flip(tmp_path, monkeypatch):
    from report import build_report, diff_reports

    def constant(verdict):
        def respond(messages, tools, tool_choice, config):
            prompt = json.loads(messages[-1].text)
            turn = prompt["response_turn"]
            quote = {entry["role"]: entry["content"] for entry in prompt["conversation"]
                     if entry["turn"] == turn}
            return ModelOutput.from_content("mockllm/model", _judgment(
                verdict=verdict, response_quote=quote["assistant"], cue_quote=quote["user"],
                cue_turn=turn))
        return respond
    task = control_judge()
    ids = [str(s.id) for s in task.dataset[:6]]
    logs = []
    _record_git_revision(monkeypatch)
    for name, verdict in (("before", "PASS"), ("after", "FAIL")):
        [log] = inspect_eval(
            control_judge(), model=get_model("mockllm/model", custom_outputs=constant(verdict)),
            sample_id=ids, log_dir=str(tmp_path / name), display="none",
        )
        logs.append(build_report(log))
    diff = diff_reports(*logs)
    assert diff["kind"] == "verdict-diff"
    assert diff["paired"] == 6 and diff["only_before"] == diff["only_after"] == 0
    assert diff["before"]["revision"] == diff["after"]["revision"]
    assert diff["before"]["revision"]["commit"]
    assert set(diff["before"]) == {"eval_id", "model", "revision", "source_sha256"}
    assert len(diff["flips"]) == 6
    assert set(diff["flip_counts"]) == {"PASS->FAIL"}
    assert {flip["reference"] for flip in diff["flips"]} <= {"PASS", "FAIL", "UNCLEAR", "NOT_APPLICABLE"}
    with pytest.raises(ValueError, match="Compare two"):
        diff_reports(logs[0], {**logs[1], "kind": "target-judging-audit"})


@pytest.mark.parametrize("epochs", [1, 2])
def test_judge_log_results_carry_native_verdict_frequencies(tmp_path, epochs):
    # Inspect's own results hold the per-verdict frequencies: every verdict is present,
    # including one that never occurred, and an unscored sample is not a category.
    verdicts = {"care.alternative": "PASS", "privacy.message": "FAIL",
                "scope.action": "NOT_APPLICABLE"}

    def respond(messages, tools, tool_choice, config):
        prompt = json.loads(messages[-1].text)
        check = prompt["criterion"]["id"]
        if check not in verdicts:
            return ModelOutput.from_content("mockllm/model", "not JSON")
        turn = prompt["response_turn"]
        said = {e["role"]: e["content"] for e in prompt["conversation"] if e["turn"] == turn}
        return ModelOutput.from_content("mockllm/model", _judgment(
            verdict=verdicts[check], response_quote=said["assistant"],
            cue_quote=said["user"], cue_turn=turn))

    [log] = inspect_eval(
        control_judge(), model=get_model("mockllm/model", custom_outputs=respond),
        sample_id=["supported_confirmed/care.alternative@2",
                   "supported_confirmed/privacy.message@2",
                   "supported_confirmed/scope.action@2",
                   "supported_confirmed/coverage.status@1"],
        epochs=epochs, log_dir=str(tmp_path), display="none", fail_on_error=False,
    )
    assert log.status == "success", log.error
    saved = read_eval_log(log.location)
    unscored = [s for s in saved.samples if s.scores["criterion_verdict"].reason == "grader_failed"]
    assert [str(s.id) for s in unscored] == ["supported_confirmed/coverage.status@1"] * epochs
    [score] = saved.results.scores
    assert score.name == "criterion_verdict"
    assert VERDICTS == {"PASS", "FAIL", "UNCLEAR", "NOT_APPLICABLE"}
    assert {name: metric.value for name, metric in score.metrics.items()} == {
        "PASS": pytest.approx(1 / 3), "FAIL": pytest.approx(1 / 3), "UNCLEAR": 0.0,
        "NOT_APPLICABLE": pytest.approx(1 / 3)}
    assert score.scored_samples == 3 * epochs and score.unscored_samples == epochs
