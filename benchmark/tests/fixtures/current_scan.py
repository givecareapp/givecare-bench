"""Create a complete synthetic scan. These records are not benchmark results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from invisiblebench.api.typesafe import DEFAULT_JUDGE_MODEL
from invisiblebench.judge import plan_scan, run_scan
from invisiblebench.scoring import generate_leaderboard
from invisiblebench.utils.benchmark_inventory import collect_public_scenario_paths, get_project_root
from invisiblebench.utils.manifest import generate_manifest

TRANSCRIPT = (
    '{"role":"user","turn":1,"content":"Hello."}\n'
    '{"role":"assistant","turn":1,"content":"I can help."}\n'
    '{"role":"user","turn":2,"content":"Thank you."}\n'
    '{"role":"assistant","turn":2,"content":"Of course."}\n'
)


class FixtureJudge:
    """Answer every question with a confident no: prohibitions pass, cues never fire."""

    def ask(self, *, model: str, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        return {"model": model, "nouls": dict.fromkeys(questions, 0.0), "input_tokens": 100}


class ScriptedJudge(FixtureJudge):
    """Answer by question name: `{"cue": 0.9}` makes every cue question yes."""

    def __init__(self, probabilities: dict[str, float], model: str | None = None):
        self.probabilities = probabilities
        self.model = model

    def ask(self, *, model: str, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": self.model or model,
            "nouls": {
                key: self.probabilities.get(key.split("/")[-1], 0.0) for key in questions
            },
            "input_tokens": 100,
        }


def write_source_run(
    root: Path,
    *,
    model_ids: tuple[str, ...] = ("fixture/model",),
    roster: list[tuple[str, str]] | None = None,
) -> Path:
    source_run = root / "source-run"
    transcripts = source_run / "transcripts"
    transcripts.mkdir(parents=True)
    if roster is None:
        roster = []
        for path in collect_public_scenario_paths():
            data = json.loads(path.read_bytes())
            roster.append(
                (
                    data.get("id") or data.get("scenario_id") or path.stem,
                    data.get("category") or path.parent.name,
                )
            )
    entries = []
    for index, model_id in enumerate(model_ids):
        for scenario_id, category in sorted(roster):
            relative = f"transcripts/{index}-{scenario_id}.jsonl"
            (source_run / relative).write_text(TRANSCRIPT)
            entries.append(
                {
                    "model": f"Fixture Model {index}",
                    "model_id": model_id,
                    "scenario_id": scenario_id,
                    "category": category,
                    "transcript_path": relative,
                }
            )
    manifest = generate_manifest(
        get_project_root(),
        list(model_ids),
        [ident for ident, _ in roster],
        transcript_policy={"temperature": 0.7},
        run_id="synthetic-fixture",
        harness="llm",
        mode="raw",
    )
    manifest.update(git_sha="a" * 40, git_dirty=False)
    (source_run / "run_manifest.json").write_text(json.dumps(manifest))
    (source_run / "transcript_run.json").write_text(
        json.dumps(
            {
                "artifact_type": "transcript_run/v1",
                "run_id": "synthetic-fixture",
                "status": "complete",
                "model_ids": list(model_ids),
                "expected_transcripts": len(entries),
                "transcript_count": len(entries),
                "error_count": 0,
                "missing_count": 0,
                "resolved_model_ids": list(model_ids),
                "resolved_providers": ["fixture"],
                "transcripts": entries,
            }
        )
    )
    return source_run


def write_current_qa_fixture(
    root: Path,
    *,
    model_ids: tuple[str, ...] = ("fixture/model",),
) -> dict[str, Path]:
    source_run = write_source_run(root, model_ids=model_ids)
    bundle = root / "scan"
    plan = plan_scan([source_run], bundle, judge_model=DEFAULT_JUDGE_MODEL)
    run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=FixtureJudge())
    candidate = generate_leaderboard(bundle)
    return {
        "scan": bundle,
        "plan": bundle / "scan_plan.json",
        "answers": bundle / "answers.jsonl",
        "ledger": bundle / "judgments.jsonl",
        "leaderboard": candidate,
        "source_run": source_run,
    }
