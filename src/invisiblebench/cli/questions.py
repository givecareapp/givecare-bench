"""Rank judge questions by how often their probability lands unresolved.

A question is unresolved when its saved probability falls strictly between
the plan's low and high thresholds: the judge model gave neither a confident
yes nor a confident no. This report is read-only and makes no model calls; it
only replays the saved answers of a completed or partial scan.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from invisiblebench.evaluation import rules
from invisiblebench.judge import load_scan
from invisiblebench.models.scan import Answer, ScanPlan


def question_report(plan: ScanPlan, answers: list[Answer]) -> list[dict[str, Any]]:
    """One row per question key, ranked by unresolved rate then answer count."""
    key_info: dict[str, tuple[str, str]] = {}
    for check in plan.checks:
        if check.cue is not None:
            key_info[rules.cue_key(check)] = (check.id, "cue")
        for name, question in check.questions.items():
            if question.type == "choice":
                # One row per option: each option key holds its own probability.
                for option in question.criteria or {}:
                    key_info[f"{rules.question_key(check, name)}={option}"] = (check.id, "choice")
                continue
            key_info[rules.question_key(check, name)] = (check.id, "question")

    thresholds = plan.judge.thresholds
    stats: dict[str, dict[str, Any]] = {}
    for answer in answers:
        if answer.answers is None:
            continue
        for key, probability in rules.probabilities(answer.answers).items():
            # A sentence question is keyed `<check>/<name>[<index>]`; report it as one question.
            if key.endswith("]") and "[" in key:
                key = key[: key.rindex("[")]
                check_id, kind = key_info[key][0], "sentence"
            else:
                check_id, kind = key_info[key]
            row = stats.setdefault(
                key,
                {
                    "question": key,
                    "check_id": check_id,
                    "kind": kind,
                    "answers": 0,
                    "unresolved": 0,
                    "yes": 0,
                    "no": 0,
                    "sum": 0.0,
                    "histogram": [0] * 10,
                },
            )
            row["answers"] += 1
            row["sum"] += probability
            verdict = rules.tri(probability, thresholds)
            if verdict is None:
                row["unresolved"] += 1
            elif verdict:
                row["yes"] += 1
            else:
                row["no"] += 1
            row["histogram"][min(int(probability * 10), 9)] += 1

    report = []
    for row in stats.values():
        count = row["answers"]
        report.append(
            {
                "question": row["question"],
                "check_id": row["check_id"],
                "kind": row["kind"],
                "answers": count,
                "unresolved": row["unresolved"],
                "unresolved_rate": round(row["unresolved"] / count, 4) if count else 0.0,
                "yes": row["yes"],
                "no": row["no"],
                "mean": round(row["sum"] / count, 4) if count else 0.0,
                "histogram": row["histogram"],
            }
        )
    report.sort(key=lambda row: (-row["unresolved_rate"], -row["answers"], row["question"]))
    return report


def questions_command(args: Any) -> int:
    json_output = bool(getattr(args, "json_output", False))
    try:
        from invisiblebench.cli.agent_commands import _load_run_metadata

        run = _load_run_metadata(args.run_id)
        if run is None:
            raise ValueError(f"run not found: {args.run_id}")
        bundle = Path(run["path"])
        plan, answers, _judgments = load_scan(bundle)
        data = question_report(plan, answers)
        limit = getattr(args, "limit", None)
        if limit is not None:
            data = data[:limit]
    except (OSError, ValueError, KeyError) as exc:
        if json_output:
            print(json.dumps({"status": "error", "command": "questions", "error": str(exc)}))
        else:
            print(f"error: {exc}")
        return 1
    if json_output:
        print(json.dumps({"status": "ok", "command": "questions", "data": data}, indent=2))
        return 0
    if not data:
        print("No questions.")
        return 0
    print(f"{'question':<48} {'answers':>7} {'unresolved':>10} {'rate':>7} {'mean':>7}")
    for row in data:
        print(
            f"{row['question']:<48} {row['answers']:>7} {row['unresolved']:>10} "
            f"{row['unresolved_rate']:>7.4f} {row['mean']:>7.4f}"
        )
    return 0
