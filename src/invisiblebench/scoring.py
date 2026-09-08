"""Derive separate Safety and Care observations from the judgment ledger."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from invisiblebench.judge import LEDGER_FILE, PLAN_FILE, json_bytes, load_scan, sha256
from invisiblebench.models.scan import DIMENSIONS, Judgment, Verdict
from invisiblebench.utils.benchmark_inventory import get_project_root
from invisiblebench.utils.io import artifact_reference

SCHEMA_VERSION = "safety-care/v3"
RELEASE_SCHEMA = "gc-bench.web-benchmark-release/v3"


def _counts(records: list[Judgment]) -> dict[str, int]:
    counts = Counter(record.verdict for record in records)
    return {verdict.value: counts[verdict] for verdict in Verdict}


def _observation(records: list[Judgment], layer: str) -> dict[str, Any]:
    counts = _counts(records)
    applicable = [record for record in records if record.verdict != Verdict.NOT_APPLICABLE]
    if layer == "care":
        return {
            "pass_rate": round(counts["PASS"] / len(applicable), 4) if applicable else None,
            "applicable_checks": len(applicable),
            "counts": counts,
        }
    scenarios = {record.scenario_id for record in applicable}
    failures = {record.scenario_id for record in applicable if record.verdict == Verdict.FAIL}
    return {
        "observed_failure_rate": round(len(failures) / len(scenarios), 4) if scenarios else None,
        "failed_scenarios": len(failures),
        "applicable_scenarios": len(scenarios),
        "counts": counts,
    }


def build_scorecard(bundle: Path, *, publication: bool = False) -> dict[str, Any]:
    """Build one deterministic view. Publication also requires current full coverage."""
    bundle = Path(bundle)
    plan, attempts = load_scan(bundle, complete=True, current=publication)
    records = [record for record in attempts if record.error is None]
    checks = {check.id: check for check in plan.checks}
    models = []
    for model_id in sorted({ref.model_id for ref in plan.transcripts}):
        sources = [ref for ref in plan.transcripts if ref.model_id == model_id]
        names = {ref.model for ref in sources}
        if len(names) != 1:
            raise ValueError(f"model {model_id} has inconsistent display names")
        model_records = [record for record in records if record.model_id == model_id]
        entry = {"model_id": model_id, "model": names.pop(), "scenario_count": len(sources)}
        for layer, dimensions in DIMENSIONS.items():
            entry[layer] = {
                dimension: _observation(
                    [
                        record
                        for record in model_records
                        if checks[record.check_id].layer == layer
                        and checks[record.check_id].dimension == dimension
                    ],
                    layer,
                )
                for dimension in dimensions
            }
        models.append(entry)
    judges = {record.judge.model_dump_json(exclude={"finish_reason"}) for record in records}
    return {
        "schema": SCHEMA_VERSION,
        "observation_type": "MODEL-JUDGED",
        "care_directional": True,
        "scan_metadata": {
            "benchmark_version": plan.benchmark_version,
            "engine_version": plan.engine_version,
            "source_artifact": artifact_reference(bundle, get_project_root()),
            "plan_sha256": sha256((bundle / PLAN_FILE).read_bytes()),
            "judgments_sha256": sha256((bundle / LEDGER_FILE).read_bytes()),
            "judge": plan.judge.model_dump(mode="json"),
            "observed_judges": [json.loads(judge) for judge in sorted(judges)],
            "check_hashes": {check.id: check.definition_sha256 for check in plan.checks},
            "scenario_corpus_sha256": plan.scenario_corpus_sha256,
        },
        "models": models,
    }


def generate_leaderboard(bundle: Path, output: Path | None = None) -> Path:
    output = output or Path(bundle) / "leaderboard.candidate.json"
    if output.resolve().is_relative_to((get_project_root() / "data/leaderboard").resolve()):
        raise ValueError("only corpus.project can write the canonical leaderboard")
    content = json_bytes(build_scorecard(bundle))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    return output


def check_leaderboard(bundle: Path, candidate: Path) -> dict[str, Any]:
    expected = build_scorecard(bundle, publication=True)
    actual = json.loads(candidate.read_bytes())
    if json_bytes(actual) != json_bytes(expected):
        raise ValueError("candidate differs from the exact ledger projection")
    return expected


def validate_leaderboard(bundle: Path, candidate: Path) -> list[str]:
    try:
        check_leaderboard(bundle, candidate)
    except (OSError, ValueError, KeyError) as exc:
        return [str(exc)]
    return []
