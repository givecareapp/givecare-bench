"""Probes share scan durability, model identity, and frozen inputs."""

import json

import pytest

from benchmark.tests.fixtures.current_scan import TRANSCRIPT, FixtureJudge
from invisiblebench.cli.archive import get_run_info
from invisiblebench.judge import load_questions
from scripts.probe_check import plan_probe, run_probe


def test_failed_probe_saves_progress_and_resumes(tmp_path):
    source = tmp_path / "conversation.jsonl"
    source.write_text(TRANSCRIPT)
    bundle = tmp_path / "probe"
    plan_probe("identity.fixture-prohibition", [source], bundle)
    assert get_run_info(bundle)["artifact_state"] == "questions_incomplete"

    class Interrupted(FixtureJudge):
        calls = 0

        def ask(self, **kwargs):
            self.calls += 1
            if self.calls == 2:
                assert len((bundle / "answers.jsonl").read_text().splitlines()) == 1
                raise RuntimeError("offline interruption")
            return super().ask(**kwargs)

    with pytest.raises(RuntimeError, match="attempt saved"):
        run_probe(bundle, max_cost_usd=1, client=Interrupted())
    rows = [json.loads(line) for line in (bundle / "answers.jsonl").read_text().splitlines()]
    assert rows[0]["error"] is None and rows[1]["error"] == "judge_api_error"
    source.write_text("The external source is no longer available")
    assert run_probe(bundle, max_cost_usd=1, client=FixtureJudge())[0].verdict.value == "PASS"
    assert len((bundle / "answers.jsonl").read_text().splitlines()) == 3
    assert get_run_info(bundle)["artifact_state"] == "questions_complete"
    assert len(load_questions(bundle)[1]) == 3
    lines = (bundle / "answers.jsonl").read_text().splitlines()
    wrong = json.loads(lines[0])
    wrong["judge"]["model"] = "other-model"
    lines[0] = json.dumps(wrong)
    (bundle / "answers.jsonl").write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="different judge"):
        load_questions(bundle)


def test_changed_probe_snapshot_is_rejected_before_inference(tmp_path):
    source = tmp_path / "conversation.jsonl"
    source.write_text(TRANSCRIPT)
    bundle = tmp_path / "probe"
    plan_probe("identity.fixture-prohibition", [source], bundle)
    next((bundle / "inputs/transcripts").glob("*.jsonl")).write_text("tampered")
    with pytest.raises(ValueError, match="bundle input changed"):
        run_probe(bundle, max_cost_usd=1, client=FixtureJudge())


@pytest.mark.parametrize("tokens", [None, -1])
def test_invalid_usage_is_a_saved_failure(tmp_path, tokens):
    source = tmp_path / "conversation.jsonl"
    source.write_text(TRANSCRIPT)
    bundle = tmp_path / "probe"
    plan_probe("identity.fixture-prohibition", [source], bundle)

    class BadUsage(FixtureJudge):
        def ask(self, **kwargs):
            response = super().ask(**kwargs)
            return response.model_copy(
                update={"usage": response.usage.model_copy(update={"input_tokens": tokens})}
            )

    with pytest.raises(RuntimeError, match="attempt saved"):
        run_probe(bundle, max_cost_usd=1, client=BadUsage())
    saved = load_questions(bundle)[1]
    assert len(saved) == 1 and saved[0].error == "invalid_judge_output"
    assert saved[0].input_tokens == 0
    assert "non-negative input usage" in saved[0].error_detail
