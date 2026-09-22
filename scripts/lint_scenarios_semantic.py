#!/usr/bin/env python3
"""Plan cue questions from authored scenarios; report only from saved answers."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from invisiblebench.api.typesafe import DEFAULT_JUDGE_MODEL
from invisiblebench.evaluation import check_registry, rules
from invisiblebench.judge import PLAN_FILE, _read_ref, plan_questions, run_questions
from invisiblebench.models.scan import QuestionPlan, RequestTask
from invisiblebench.models.scenario import Scenario
from invisiblebench.utils.benchmark_inventory import collect_scenario_paths


@dataclass
class LoadedScenario:
    path: Path
    scenario: Scenario

    @property
    def scenario_id(self):
        return self.scenario.scenario_id


def load_scenario(path: Path) -> LoadedScenario:
    return LoadedScenario(path, Scenario.model_validate_json(path.read_bytes()))


def user_cue_checks(checks, ids):
    unknown = set(ids) - checks.keys()
    if unknown:
        raise ValueError(f"unknown declared checks: {sorted(unknown)}")
    return {i for i in ids if checks[i].cue is not None and checks[i].cue.role == "user"}


def query_checks(loaded, checks):
    own = {s.scenario_id: user_cue_checks(checks, s.scenario.eligible_modes) for s in loaded}
    groups = {}
    for item in loaded:
        if item.scenario.contrast_group:
            groups.setdefault(item.scenario.contrast_group, set()).update(own[item.scenario_id])
    return own, {
        s.scenario_id: groups.get(s.scenario.contrast_group, own[s.scenario_id]) for s in loaded
    }


def lint_tasks(loaded, checks):
    _, queries = query_checks(loaded, checks)
    tasks = []
    for item in loaded:
        transcript = [
            {"role": "user", "turn": t.turn_number, "content": t.user_message}
            for t in item.scenario.all_turns
        ]
        selected = [checks[i] for i in sorted(queries[item.scenario_id])]
        for turn in transcript:
            request = rules.build_request(selected, transcript, "user", turn["turn"])
            if request["questions"]:
                tasks.append(
                    RequestTask(
                        model_id="semantic-lint",
                        scenario_id=item.scenario_id,
                        role="user",
                        turn=turn["turn"],
                        **request,
                    )
                )
    return tasks


def plan_lint(paths, output, *, model=DEFAULT_JUDGE_MODEL):
    loaded, checks = [load_scenario(p) for p in paths], check_registry.load_checks()
    query_checks(loaded, checks)
    sources = {f"inputs/scenarios/{item.scenario_id}.json": item.path for item in loaded}
    if len(sources) != len(loaded):
        raise ValueError("duplicate scenario IDs")
    for check_id in set().union(*(set(item.scenario.eligible_modes) for item in loaded)):
        check = checks[check_id]
        relative = f"{check.layer}/{check.dimension}/{check.id}.yaml"
        sources[f"inputs/checks/{relative}"] = check_registry.CHECKS_DIR / relative
    return plan_questions(output, lint_tasks(loaded, checks), model=model, sources=sources)


@dataclass
class ScenarioResult:
    loaded: LoadedScenario
    own_check_ids: set[str]
    per_turn: dict[str, dict[int, float]]


def build_scenario_results(loaded, checks, answers):
    own, queries = query_checks(loaded, checks)
    saved = {(a.scenario_id, a.turn): a.answers for a in answers if a.error is None}
    return [
        ScenarioResult(
            item,
            own[item.scenario_id],
            {
                cid: {
                    t.turn_number: saved[item.scenario_id, t.turn_number][
                        rules.cue_key(checks[cid])
                    ].noul
                    for t in item.scenario.all_turns
                }
                for cid in queries[item.scenario_id]
            },
        )
        for item in loaded
    ]


def strongest(per_turn):
    if not per_turn:
        return 0.0, None
    turn = max(per_turn, key=per_turn.get)
    return per_turn[turn], turn


def scenario_report(result, thresholds):
    entries = []
    for cid in sorted(result.own_check_ids):
        probability, turn = strongest(result.per_turn[cid])
        entry = {"check_id": cid, "max_probability": probability, "max_turn": turn}
        if probability < thresholds.high:
            entry["flag"] = "no_cue" if probability <= thresholds.low else "weak_cue"
        entries.append(entry)
    return {
        "scenario_id": result.loaded.scenario_id,
        "path": str(result.loaded.path),
        "checks": entries,
    }


def contrast_report(results, thresholds):
    groups = {}
    for result in results:
        if group := result.loaded.scenario.contrast_group:
            groups.setdefault(group, []).append(result)
    report = {}
    for name, members in sorted(groups.items()):
        anchor = next((m for m in members if m.loaded.scenario.contrast_variable == "anchor"), None)
        ids = sorted(set().union(*(m.per_turn.keys() for m in members)))
        table = [
            {
                "check_id": cid,
                **{
                    m.loaded.scenario_id: {
                        "contrast_variable": m.loaded.scenario.contrast_variable,
                        "max_probability": strongest(m.per_turn[cid])[0],
                        "max_turn": strongest(m.per_turn[cid])[1],
                    }
                    for m in members
                },
            }
            for cid in ids
        ]
        flags = []
        if anchor is not None:
            for member in members:
                if member is anchor:
                    continue
                for cid in ids:
                    a, b = cid in anchor.own_check_ids, cid in member.own_check_ids
                    if not (a or b):
                        continue
                    av, bv = strongest(anchor.per_turn[cid])[0], strongest(member.per_turn[cid])[0]
                    expectation = "preserved" if a and b else "removed" if a else "added"
                    separated = (
                        (av >= thresholds.high) == (bv >= thresholds.high)
                        if a and b
                        else (
                            av >= thresholds.high and bv < thresholds.high
                            if a
                            else bv >= thresholds.high
                        )
                    )
                    if not separated:
                        flags.append(
                            {
                                "variant_scenario_id": member.loaded.scenario_id,
                                "check_id": cid,
                                "expectation": expectation,
                                "anchor_probability": av,
                                "variant_probability": bv,
                                "flag": "contrast_not_separated",
                            }
                        )
        report[name] = {
            "anchor": anchor.loaded.scenario_id if anchor else None,
            "members": [m.loaded.scenario_id for m in members],
            "table": table,
            "flags": flags,
        }
    return report


def execute(bundle: Path, *, max_cost_usd: float, client=None):
    plan = QuestionPlan.model_validate_json((bundle / PLAN_FILE).read_bytes())
    for ref in plan.inputs:
        _read_ref(bundle, ref)
    loaded = [
        load_scenario(bundle / ref.path)
        for ref in plan.inputs
        if ref.path.startswith("inputs/scenarios/")
    ]
    checks = {
        c.id: c
        for ref in plan.inputs
        if ref.path.endswith(".yaml")
        for c in [check_registry.load_check(bundle / ref.path)]
    }
    if lint_tasks(loaded, checks) != plan.tasks:
        raise ValueError("lint inputs differ from the frozen requests")
    with run_questions(bundle, max_cost_usd=max_cost_usd, client=client) as answers:
        results = build_scenario_results(loaded, checks, answers)
        return {
            "scenarios": [scenario_report(r, plan.judge.thresholds) for r in results],
            "contrast_groups": contrast_report(results, plan.judge.thresholds),
            "completed_requests": sum(a.error is None for a in answers),
            "input_tokens": sum(a.input_tokens for a in answers),
            "cost_usd": sum(a.cost_usd for a in answers),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--model", default=DEFAULT_JUDGE_MODEL)
    plan.add_argument("--scenario")
    plan.add_argument("--limit", type=int)
    plan.add_argument("--include-private", action="store_true")
    run = sub.add_parser("run")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--max-cost-usd", type=float, required=True)
    run.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.command == "plan":
        paths = collect_scenario_paths(include_confidential=args.include_private)
        paths = [p for p in paths if args.scenario is None or args.scenario in str(p)]
        result = plan_lint(paths[: args.limit], args.output, model=args.model)
        print(
            f"Plan: {args.output / PLAN_FILE}; requests: {len(result.tasks)}; estimate: ${result.estimated_cost_usd}"
        )
        return 0
    if args.plan.name != PLAN_FILE:
        parser.error("--plan must name scan_plan.json")
    result = execute(args.plan.parent, max_cost_usd=args.max_cost_usd)
    print(json.dumps(result, indent=2))
    return int(
        args.strict
        and (
            any(c.get("flag") for s in result["scenarios"] for c in s["checks"])
            or any(g["flags"] for g in result["contrast_groups"].values())
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
