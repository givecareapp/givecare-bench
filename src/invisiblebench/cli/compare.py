"""Compare two validated scans. Differences are observations, not judge accuracy."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from invisiblebench.evaluation.rules import probabilities, tri
from invisiblebench.judge import load_scan


def compare_ledgers(old_bundle: Path, new_bundle: Path) -> dict[str, Any]:
    old_plan, old_answers, old_judgments = load_scan(old_bundle, complete=True)
    new_plan, new_answers, new_judgments = load_scan(new_bundle, complete=True)
    old = {j.key: j for j in old_judgments}
    new = {j.key: j for j in new_judgments}
    shared = sorted(old.keys() & new.keys())
    flips = [{"model_id": key[0], "scenario_id": key[1], "check_id": key[2],
              "old": old[key].verdict.value, "new": new[key].verdict.value}
             for key in shared if old[key].verdict != new[key].verdict]
    prior = {a.key: a for a in old_answers if a.error is None}
    differences = []
    for answer in new_answers:
        before = prior.get(answer.key)
        if answer.error is not None or before is None or answer.input_sha256 != before.input_sha256:
            continue
        previous = probabilities(before.answers)
        for key, value in probabilities(answer.answers).items():
            differences.append({"question": key, "delta": abs(value - previous[key]),
                                "band_changed": tri(value, new_plan.judge.thresholds) != tri(previous[key], old_plan.judge.thresholds)})
    return {
        "old_judge": old_plan.judge.model, "new_judge": new_plan.judge.model,
        "shared": len(shared), "old_only": len(old.keys() - new.keys()),
        "new_only": len(new.keys() - old.keys()), "verdict_flips": flips,
        "transitions": dict(Counter(f"{old[k].verdict.value}->{new[k].verdict.value}" for k in shared)),
        "matching_request_probabilities": len(differences),
        "max_abs_delta": max((d["delta"] for d in differences), default=0.0),
        "band_changes": sum(d["band_changed"] for d in differences),
        "accuracy_claim": False,
    }


def compare_command(args: Any) -> int:
    try:
        report = compare_ledgers(Path(args.old), Path(args.new))
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "error", "command": "compare", "error": str(exc)}))
        return 1
    print(json.dumps({"status": "ok", "command": "compare", "data": report}, indent=2))
    return 0
