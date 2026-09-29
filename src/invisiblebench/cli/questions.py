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

from typesafe_sdk import NoulAnswer

from invisiblebench.evaluation import requests, rules
from invisiblebench.judge import _conversations, load_scan
from invisiblebench.models.scan import Answer, Judgment, ScanPlan, Verdict


def observation_family(key: str) -> str:
    if key.endswith("]") and "[" in key:
        return key[: key.rindex("[")]
    return "/".join(part for part in key.split("/") if not part.isdigit())


def judgment_effects(
    bundle: Path, plan: ScanPlan, judgments: list[Judgment]
) -> dict[str, list[dict[str, Any]]]:
    """Resolve one consumed observation at a time through the original rule engine.

    Effects mean narrowing possible verdicts, not independent correctness. Other
    unresolved observations stay unresolved; no exponential assignment search.
    """
    effects: dict[str, list[dict[str, Any]]] = {}
    conversations = _conversations(bundle, plan)
    checks = {check.id: check for check in plan.checks}
    for judgment in judgments:
        if judgment.verdict != Verdict.UNCLEAR:
            continue
        transcript, memory = conversations[judgment.model_id, judgment.scenario_id]
        saved = {}
        for key, answer in judgment.answers.items():
            location, observation = key.split("/", 1)
            role, number = location.split(":")
            saved.setdefault((role, int(number)), {})[observation] = answer
        check = checks[judgment.check_id]

        def outcomes(
            check=check, transcript=transcript, saved=saved, judgment=judgment, memory=memory
        ):
            return sorted(
                v.value
                for v in rules.analyze(
                    check,
                    transcript,
                    saved,
                    plan.judge.thresholds,
                    model_id=judgment.model_id,
                    scenario_id=judgment.scenario_id,
                    plan_sha256=judgment.plan_sha256,
                    memory_declared=memory.persistent_memory,
                )[1]
            )

        possible = outcomes()
        for (role, number), observations in saved.items():
            for key, answer in list(observations.items()):
                if isinstance(answer, NoulAnswer):
                    if rules.tri(answer.noul, plan.judge.thresholds) is not None:
                        continue
                    resolutions = {"no": NoulAnswer(noul=0.0), "yes": NoulAnswer(noul=1.0)}
                else:
                    if max(answer.probabilities.values()) >= plan.judge.thresholds.high:
                        continue
                    resolutions = {
                        option: answer.model_copy(
                            update={
                                "choice": option,
                                "probabilities": {
                                    name: float(name == option) for name in answer.probabilities
                                },
                            }
                        )
                        for option, p in answer.probabilities.items()
                        if p > 0
                    }
                resolved = {}
                for label, value in resolutions.items():
                    observations[key] = value
                    resolved[label] = outcomes()
                observations[key] = answer
                if all(value == possible for value in resolved.values()):
                    continue
                keys = (
                    [key]
                    if isinstance(answer, NoulAnswer)
                    else [f"{key}={option}" for option in resolutions]
                )
                for reported_key in keys:
                    effects.setdefault(observation_family(reported_key), []).append(
                        {
                            "model_id": judgment.model_id,
                            "scenario_id": judgment.scenario_id,
                            "check_id": check.id,
                            "role": role,
                            "turn": number,
                            "observation": key,
                            "possible_verdicts": possible,
                            "when_resolved": resolved,
                        }
                    )
    return effects


def question_report(plan: ScanPlan, answers: list[Answer]) -> list[dict[str, Any]]:
    """One row per question key, ranked by unresolved rate then answer count."""
    key_info: dict[str, tuple[str, str]] = {}
    for check in plan.checks:
        if check.cue is not None:
            key_info[requests.cue_key(check)] = (check.id, "cue")
        for name, question in check.questions.items():
            if question.type == "choice":
                # One row per option: each option key holds its own probability.
                for option in question.criteria or {}:
                    key_info[f"{requests.question_key(check, name)}={option}"] = (
                        check.id,
                        "choice",
                    )
                continue
            key_info[requests.question_key(check, name)] = (check.id, "question")

    check_ids = {check.id for check in plan.checks}
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
            elif key in key_info:
                check_id, kind = key_info[key]
            else:
                # A bound observation (crisis reference, task detail, source claim)
                # carries instance indexes; report it as one observation family.
                key = observation_family(key)
                check_id, kind = key.split("/", 1)[0], "bound"
                if check_id not in check_ids:
                    raise KeyError(key)
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
        plan, answers, judgments = load_scan(bundle)
        data = question_report(plan, answers)
        effects = judgment_effects(bundle, plan, judgments)
        for row in data:
            row["effects"] = effects.get(row["question"], [])
            row["affected_judgments"] = len(
                {
                    (effect["model_id"], effect["scenario_id"], effect["check_id"])
                    for effect in row["effects"]
                }
            )
            row["judgment_analysis"] = "complete" if judgments else "unavailable: partial scan"
        data.sort(
            key=lambda row: (-row["affected_judgments"], -row["unresolved_rate"], row["question"])
        )
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
    print("Affected = judgments whose possible verdicts can narrow when one answer resolves.")
    print(f"{'question':<48} {'answers':>7} {'unresolved':>10} {'rate':>7} {'affected':>8}")
    for row in data:
        print(
            f"{row['question']:<48} {row['answers']:>7} {row['unresolved']:>10} "
            f"{row['unresolved_rate']:>7.4f} {row['affected_judgments']:>8}"
        )
    return 0
