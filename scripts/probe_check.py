#!/usr/bin/env python3
"""Plan one check against transcripts, then run the frozen, budgeted probe."""

from __future__ import annotations

import argparse
from pathlib import Path

from invisiblebench.api.typesafe import DEFAULT_JUDGE_MODEL
from invisiblebench.evaluation import check_registry, rules
from invisiblebench.evaluation.check_registry import load_check
from invisiblebench.judge import (
    PLAN_FILE,
    _read_ref,
    _transcript,
    plan_questions,
    run_questions,
    sha256,
)
from invisiblebench.models.scan import QuestionPlan, RequestTask


def plan_probe(check_id: str, transcripts: list[Path], output: Path, *, model=DEFAULT_JUDGE_MODEL):
    paths = list(check_registry.CHECKS_DIR.rglob(f"{check_id}.yaml"))
    if len(paths) != 1:
        raise ValueError(f"unknown check: {check_id}")
    check = load_check(paths[0])
    sources = {f"inputs/checks/{check.layer}/{check.dimension}/{check.id}.yaml": paths[0]}
    tasks = []
    for index, path in enumerate(transcripts):
        scenario = f"{index}-{path.stem}"
        sources[f"inputs/transcripts/{scenario}.jsonl"] = path
        transcript = _transcript(path.read_bytes())
        for role, turn in rules.request_turns(transcript):
            request = rules.build_request([check], transcript, role, turn)
            if request["questions"]:
                tasks.append(
                    RequestTask(
                        model_id=check.id, scenario_id=scenario, role=role, turn=turn, **request
                    )
                )
    return plan_questions(output, tasks, model=model, sources=sources)


def run_probe(bundle: Path, *, max_cost_usd: float, client=None):
    content = (bundle / PLAN_FILE).read_bytes()
    plan = QuestionPlan.model_validate_json(content)
    for ref in plan.inputs:
        _read_ref(bundle, ref)
    check = load_check(next(bundle / ref.path for ref in plan.inputs if ref.path.endswith(".yaml")))
    transcripts = {
        Path(ref.path).stem: _transcript(_read_ref(bundle, ref))
        for ref in plan.inputs
        if ref.path.endswith(".jsonl")
    }
    for task in plan.tasks:
        if task.model_id != check.id or task.request != rules.build_request(
            [check],
            transcripts[task.scenario_id],
            task.role,
            task.turn,
        ):
            raise ValueError("probe inputs differ from the frozen requests")
    with run_questions(bundle, max_cost_usd=max_cost_usd, client=client) as answers:
        judgments = []
        for scenario, transcript in transcripts.items():
            saved = {
                (a.role, a.turn): a.answers
                for a in answers
                if a.scenario_id == scenario and a.error is None
            }
            judgments.append(
                rules.derive(
                    check,
                    transcript,
                    saved,
                    plan.judge.thresholds,
                    model_id=check.id,
                    scenario_id=scenario,
                    plan_sha256=sha256(content),
                )
            )
        return judgments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("check_id")
    plan.add_argument("transcripts", nargs="+", type=Path)
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--model", default=DEFAULT_JUDGE_MODEL)
    run = commands.add_parser("run")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--max-cost-usd", type=float, required=True)
    args = parser.parse_args()
    if args.command == "plan":
        result = plan_probe(args.check_id, args.transcripts, args.output, model=args.model)
        print(
            f"Plan: {args.output / PLAN_FILE}; requests: {len(result.tasks)}; estimate: ${result.estimated_cost_usd}"
        )
    else:
        if args.plan.name != PLAN_FILE:
            parser.error("--plan must name scan_plan.json")
        for judgment in run_probe(args.plan.parent, max_cost_usd=args.max_cost_usd):
            print(judgment.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
