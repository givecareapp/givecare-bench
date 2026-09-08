"""Build a complete, neutral scan fixture for current QA and driver tests.

The fixture uses the live scenario and check rosters, but it writes no scenario
text or judge prompt.  Its verdicts are contract fixtures, not benchmark data.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from invisiblebench.evaluation.check_registry import (
    check_definition_hashes,
    check_prompt_hashes,
    load_checks,
)
from invisiblebench.evaluation.verifiers.llm_verifier import (
    _format_transcript_for_prompt,
    prompt_for_check,
)
from invisiblebench.judge import attach_scan_provenance, build_scan_plan
from invisiblebench.utils.benchmark_inventory import (
    collect_public_scenario_paths,
    get_benchmark_version,
    get_project_root,
)
from invisiblebench.utils.manifest import scenario_corpus_hash
from invisiblebench.version import ENGINE_VERSION, SCANNED_ROW_CONTRACT_VERSION
from scripts.generate_leaderboard import generate_leaderboard


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _scenario_roster() -> list[tuple[str, str]]:
    roster: list[tuple[str, str]] = []
    for path in collect_public_scenario_paths(get_project_root()):
        data = json.loads(path.read_text(encoding="utf-8"))
        scenario_id = str(data.get("id") or data.get("scenario_id") or path.stem)
        category = str(data.get("category") or path.parent.name)
        roster.append((scenario_id, category))
    return sorted(roster)


def _write_transcript(path: Path) -> list[dict[str, Any]]:
    transcript = [
        {"role": "user", "turn": 1, "content": "Hello."},
        {"role": "assistant", "turn": 1, "content": "I can help."},
    ]
    path.write_text(
        "".join(json.dumps(turn, ensure_ascii=False) + "\n" for turn in transcript),
        encoding="utf-8",
    )
    return transcript


def write_current_qa_fixture(
    root: Path,
    *,
    model_id: str = "fixture/model",
    judge_model: str = "fixture/judge",
) -> dict[str, Path]:
    """Write a complete current scan and return paths for QA or driver tests."""

    project_root = get_project_root()
    source_run = root / "source-run"
    transcript_dir = source_run / "transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    roster = _scenario_roster()
    pairs: list[dict[str, Any]] = []
    transcripts: dict[str, list[dict[str, Any]]] = {}
    for scenario_id, category in roster:
        path = transcript_dir / f"{scenario_id}.jsonl"
        transcripts[scenario_id] = _write_transcript(path)
        pairs.append(
            {
                "transcript_path": path.resolve(),
                "model": "Fixture Model",
                "model_id": model_id,
                "scenario_id": scenario_id,
                "category": category,
            }
        )

    config_hash = _sha256((project_root / "benchmark/configs/scoring.yaml").read_bytes())
    scenario_ids = [scenario_id for scenario_id, _category in roster]
    (source_run / "run_manifest.json").write_text(
        json.dumps(
            {
                "schema": "invisiblebench-run-manifest/v2",
                "run_id": "fixture-run",
                "git_sha": "a" * 40,
                "git_dirty": False,
                "benchmark_version": get_benchmark_version(project_root),
                "scenario_hash": scenario_corpus_hash(project_root),
                "scenario_ids": scenario_ids,
                "scoring_config_hash": config_hash,
                "check_definition_hashes": check_definition_hashes(),
                "model_ids": [model_id],
                "harness": "fixture",
                "mode": "transcript_only",
                "transcript_policy": {"temperature": 0.7},
            }
        ),
        encoding="utf-8",
    )
    (source_run / "transcript_run.json").write_text(
        json.dumps(
            {
                "artifact_type": "transcript_run/v1",
                "run_id": "fixture-run",
                "status": "complete",
                "model_ids": [model_id],
                "expected_transcripts": len(pairs),
                "transcript_count": len(pairs),
                "error_count": 0,
                "missing_count": 0,
                "resolved_model_ids": [model_id],
                "resolved_providers": ["fixture"],
                "transcripts": [
                    {
                        **{key: pair[key] for key in ("model", "model_id", "scenario_id", "category")},
                        "transcript_path": f"transcripts/{pair['scenario_id']}.jsonl",
                    }
                    for pair in pairs
                ],
            }
        ),
        encoding="utf-8",
    )

    checks = load_checks()
    prompt_hashes = check_prompt_hashes()
    mode_results_by_scenario: dict[str, list[dict[str, Any]]] = {}
    for scenario_id, _category in roster:
        transcript = transcripts[scenario_id]
        mode_results: list[dict[str, Any]] = []
        for check_id, check in checks.items():
            messages = [
                {"role": "system", "content": prompt_for_check(check)},
                {"role": "user", "content": _format_transcript_for_prompt(transcript)},
            ]
            decision = {
                "verdict": "PASS",
                "rationale": "The fixture response meets the recorded criterion.",
                "evidence": [],
            }
            mode_results.append(
                {
                    "mode_id": check_id,
                    "eligible": True,
                    "verdict": "PASS",
                    "severity": check["severity"],
                    "layer": check["layer"],
                    "dimension": check["dimension"],
                    "scorer_type": "llm_verifier",
                    "scorer_version": ENGINE_VERSION,
                    "prompt_hash": prompt_hashes[check_id],
                    "evidence": [],
                    "rationale": decision["rationale"],
                    "rationale_code": None,
                    "judge": {
                        "model": judge_model,
                        "resolved_model": judge_model,
                        "provider": "fixture",
                        "temperature": 0.0,
                        "max_tokens": 4000,
                        "context_policy": "full_ordered",
                    },
                    "extra": {
                        "raw_response": json.dumps(decision, separators=(",", ":")),
                        "input_sha256": _sha256(
                            json.dumps(
                                messages,
                                ensure_ascii=False,
                                sort_keys=True,
                            ).encode()
                        ),
                    },
                }
            )
        mode_results_by_scenario[scenario_id] = mode_results

    scan_path = root / "per_run.jsonl"
    with scan_path.open("w", encoding="utf-8") as handle:
        for pair in pairs:
            mode_results = mode_results_by_scenario[pair["scenario_id"]]
            row = {
                **pair,
                "transcript_path": str(pair["transcript_path"]),
                "contract_version": SCANNED_ROW_CONTRACT_VERSION,
                "mode_results": mode_results,
                "engine_version": ENGINE_VERSION,
                "eligible_count": len(mode_results),
                "resolved_count": len(mode_results),
                "unclear_count": 0,
                "coverage_rate": 1.0,
            }
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    plan = attach_scan_provenance(
        build_scan_plan(pairs, checks, judge_model=judge_model),
        run_dirs=[source_run],
        transcript_pairs=pairs,
        selection={"filter": None, "limit_per_source_run": None, "source_run_count": 1},
    )
    plan_path = root / "scan_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    leaderboard_path = generate_leaderboard(scan_path, root / "leaderboard")
    return {
        "scan": scan_path,
        "plan": plan_path,
        "leaderboard": leaderboard_path,
        "source_run": source_run,
    }


__all__ = ["write_current_qa_fixture"]
