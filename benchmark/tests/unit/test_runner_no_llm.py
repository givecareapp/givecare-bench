"""CLI runner tests for no-LLM scorer mode."""

from __future__ import annotations

from invisiblebench.cli import runner


def test_main_passes_no_llm_to_raw_benchmark(monkeypatch) -> None:
    captured = {}

    def fake_run_benchmark(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(runner, "run_benchmark", fake_run_benchmark)

    exit_code = runner.main(["--no-llm", "--dry-run", "-m", "deepseek"])

    assert exit_code == 0
    assert captured["allow_llm"] is False


def test_main_passes_no_llm_to_givecare_harness(monkeypatch) -> None:
    captured = {}

    def fake_run_givecare_eval(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(runner, "run_givecare_eval", fake_run_givecare_eval)

    exit_code = runner.main(["--harness", "givecare", "--mode", "live", "--no-llm", "--dry-run"])

    assert exit_code == 0
    assert captured["allow_llm"] is False


def test_generate_transcript_logs_branch_method_and_evidence(tmp_path, monkeypatch) -> None:
    import json

    scenario_path = tmp_path / "scenario.json"
    output_path = tmp_path / "transcript.jsonl"
    scenario_path.write_text(
        json.dumps(
            {
                "path": str(scenario_path),
                "turns": [
                    {"turn_number": 1, "user_message": "Hello"},
                    {
                        "turn_number": 2,
                        "user_message": "Default",
                        "branches": [
                            {
                                "branch_id": "matched",
                                "condition": {"type": "contains_any", "values": ["hello"]},
                                "user_message": "Branched",
                            }
                        ],
                    },
                ],
            }
        )
    )

    class FakeClient:
        def __init__(self):
            self.responses = iter(["hello there", "all set"])

        def call_model(self, **kwargs):
            return {"response": next(self.responses)}

    monkeypatch.setattr(runner.time, "sleep", lambda *_args, **_kwargs: None)

    runner.generate_transcript(
        "openai/test-model",
        {"path": str(scenario_path)},
        FakeClient(),
        output_path,
        allow_llm=False,
    )

    rows = [json.loads(line) for line in output_path.read_text().splitlines()]
    second_user = rows[2]
    assert second_user["branch_id"] == "matched"
    assert second_user["branch_method"] == "lexical"
    assert second_user["branch_evidence"] == "Matched keyword: hello"
