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
                # Billed with known usage, but missing its answers: retryable.
                return super().ask(**kwargs).model_copy(update={"answers": {}})
            return super().ask(**kwargs)

    with pytest.raises(RuntimeError, match="attempt saved"):
        run_probe(bundle, max_cost_usd=1, client=Interrupted())
    rows = [json.loads(line) for line in (bundle / "answers.jsonl").read_text().splitlines()]
    assert rows[0]["error"] is None and rows[1]["error"] == "invalid_judge_output"
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


@pytest.mark.parametrize("unknown", [False, True])
def test_multiple_requests_in_one_turn_resume_by_exact_identity(
    tmp_path, published_checks, unknown
):
    from invisiblebench.api.client import CostBudgetExceededError, cost_tracker

    source = tmp_path / "conversation.jsonl"
    source.write_text(TRANSCRIPT)
    bundle = tmp_path / "probe"
    plan = plan_probe("attunement.advice-first", [source], bundle)
    assert plan.tasks[1].role == plan.tasks[2].role == "assistant"
    assert plan.tasks[1].turn == plan.tasks[2].turn

    class Interrupted(FixtureJudge):
        calls = 0

        def ask(self, **kwargs):
            self.calls += 1
            if self.calls == 3:
                if unknown:
                    raise KeyboardInterrupt("sent but no outcome")
                raise CostBudgetExceededError("refused before dispatch")
            cost_tracker.record(kwargs["model"], 0, 0, actual_cost=0.00001)
            return super().ask(**kwargs)

    first = Interrupted()
    with pytest.raises(KeyboardInterrupt if unknown else CostBudgetExceededError):
        run_probe(bundle, max_cost_usd=1, client=first)
    retained = (bundle / "answers.jsonl").read_bytes()
    _, saved = load_questions(bundle)
    assert len(saved) == 2
    assert len({answer.key for answer in saved}) == 2
    if unknown:
        with pytest.raises(ValueError, match="no automatic resume"):
            run_probe(bundle, max_cost_usd=1, client=first)
        assert first.calls == 3
    else:
        run_probe(bundle, max_cost_usd=1, client=FixtureJudge())
        _, saved = load_questions(bundle)
        assert len(saved) == len(plan.tasks)
        assert sum(a.cost_usd for a in saved) == pytest.approx(0.00002)
    assert (bundle / "answers.jsonl").read_bytes().startswith(retained)


def test_changed_probe_snapshot_is_rejected_before_inference(tmp_path):
    source = tmp_path / "conversation.jsonl"
    source.write_text(TRANSCRIPT)
    bundle = tmp_path / "probe"
    plan_probe("identity.fixture-prohibition", [source], bundle)
    next((bundle / "inputs/transcripts").glob("*.jsonl")).write_text("tampered")
    with pytest.raises(ValueError, match="bundle input changed"):
        run_probe(bundle, max_cost_usd=1, client=FixtureJudge())


@pytest.mark.parametrize("tokens", [None, -1])
def test_invalid_usage_is_unknown_cost_and_blocks_resume(tmp_path, tokens):
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

    with pytest.raises(RuntimeError, match="outcome unknown"):
        run_probe(bundle, max_cost_usd=1, client=BadUsage())
    assert load_questions(bundle)[1] == []
    unknown = json.loads((bundle / "attempts.jsonl").read_text().splitlines()[-1])
    assert unknown["event"] == "unknown"
    assert "non-negative input usage" in unknown["detail"]
    assert unknown["response"]["usage"]["input_tokens"] == tokens
    with pytest.raises(ValueError, match="no automatic resume"):
        run_probe(bundle, max_cost_usd=1, client=FixtureJudge())
