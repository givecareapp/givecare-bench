#!/usr/bin/env python3
"""Plan exemplar requests, refresh from a saved plan, or verify committed answers offline."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter
from typesafe_sdk import Answer as TypedAnswer

from invisiblebench.api.typesafe import DEFAULT_JUDGE_MODEL, validate_answers
from invisiblebench.evaluation import rules
from invisiblebench.evaluation.check_registry import CHECKS_DIR, load_checks
from invisiblebench.judge import PLAN_FILE, plan_questions, run_questions
from invisiblebench.models.scan import Check, MemoryContext, QuestionPlan, RequestTask, Thresholds, Verdict

EXAMPLES = "examples.jsonl"
ANSWERS = "examples.answers.jsonl"
VERDICTS = {v.value for v in Verdict}
ANSWER_MAP = TypeAdapter(dict[str, TypedAnswer])


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def load_examples(root: Path, checks: dict[str, Check]) -> dict[Path, list[dict[str, Any]]]:
    found, seen = {}, set()
    for directory in sorted(p for p in root.glob("*/*") if p.is_dir()):
        rows = _read_jsonl(directory / EXAMPLES)
        for row in rows:
            if not {"id", "check_id", "expected", "transcript"} <= row.keys():
                raise ValueError(f"{directory}: exemplar missing required fields")
            if row["id"] in seen:
                raise ValueError(f"duplicate exemplar id: {row['id']}")
            seen.add(row["id"])
            check = checks.get(row["check_id"])
            if check is None or (check.layer, check.dimension) != (directory.parent.name, directory.name):
                raise ValueError(f"{row['id']}: unknown check or wrong directory")
            if row["expected"] not in VERDICTS or not any(t.get("role") == "assistant" for t in row["transcript"]):
                raise ValueError(f"{row['id']}: invalid expected verdict or missing assistant")
        found[directory] = rows
    return found


def requests_for(check: Check, exemplar: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    memory = MemoryContext(persistent_memory=bool(exemplar.get("memory_declared", False)))
    return {(role, turn): request for role, turn in rules.request_turns(exemplar["transcript"])
            if (request := rules.build_request([check], exemplar["transcript"], role, turn, memory))["questions"]}


def _answer_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str, int], dict[str, Any]]:
    index = {(row["id"], row["role"], row["turn"]): row for row in rows}
    if len(index) != len(rows):
        raise ValueError("duplicate exemplar answer")
    return index


def verify(root: Path, checks: dict[str, Check], thresholds: Thresholds, *, model: str = DEFAULT_JUDGE_MODEL):
    failures = []
    totals = {"exemplars": 0, "passed": 0, "mismatch": 0, "stale": 0, "uncovered": 0}
    covered = defaultdict(set)
    for directory, exemplars in load_examples(root, checks).items():
        answers = _answer_index(_read_jsonl(directory / ANSWERS))
        for exemplar in exemplars:
            totals["exemplars"] += 1
            check = checks[exemplar["check_id"]]
            saved = {}
            for (role, turn), request in requests_for(check, exemplar).items():
                row = answers.get((exemplar["id"], role, turn))
                if row is None or "answers" not in row or row["input_sha256"] != rules.input_hash(request) or row["model"] != model:
                    totals["stale"] += 1
                    failures.append(f"STALE    {exemplar['id']}: plan and refresh its answers")
                    break
                typed = ANSWER_MAP.validate_python(row["answers"])
                validate_answers(typed, request["questions"])
                saved[role, turn] = typed
            else:
                judgment = rules.derive(check, exemplar["transcript"], saved, thresholds,
                                        model_id="exemplar", scenario_id=exemplar["id"], plan_sha256="0" * 64,
                                        memory_declared=bool(exemplar.get("memory_declared", False)))
                covered[check.id].add(exemplar["expected"])
                if judgment.verdict.value == exemplar["expected"]:
                    totals["passed"] += 1
                else:
                    totals["mismatch"] += 1
                    failures.append(f"MISMATCH {exemplar['id']}: expected {exemplar['expected']}, "
                                    f"derived {judgment.verdict.value}: {judgment.rationale}")
    for check_id in sorted(checks):
        expected = covered[check_id]
        if "FAIL" not in expected or not expected & {"PASS", "NOT_APPLICABLE"}:
            totals["uncovered"] += 1
            failures.append(f"UNCOVERED {check_id}: needs FAIL and PASS or NOT_APPLICABLE exemplars")
    return failures, totals


def plan_refresh(root: Path, checks: dict[str, Check], bundle: Path, *, model: str = DEFAULT_JUDGE_MODEL, only: str | None = None):
    if only is not None and only not in checks:
        raise ValueError(f"unknown check: {only}")
    tasks = []
    for directory, exemplars in load_examples(root, checks).items():
        existing = _answer_index(_read_jsonl(directory / ANSWERS))
        for exemplar in exemplars:
            check = checks[exemplar["check_id"]]
            if only is not None and check.id != only:
                continue
            for (role, turn), request in requests_for(check, exemplar).items():
                row = existing.get((exemplar["id"], role, turn))
                if row is not None and "answers" in row and row["input_sha256"] == rules.input_hash(request) and row["model"] == model:
                    continue
                tasks.append(RequestTask(model_id=check.id, scenario_id=exemplar["id"], role=role, turn=turn, **request))
    return plan_questions(bundle, tasks, model=model) if tasks else None


def refresh(root: Path, checks: dict[str, Check], bundle: Path, *, max_cost_usd: float, client: Any = None):
    plan = QuestionPlan.model_validate_json((bundle / PLAN_FILE).read_bytes())
    examples = load_examples(root, checks)
    current = {e["id"]: (directory, e) for directory, rows in examples.items() for e in rows}
    for task in plan.tasks:
        if task.scenario_id not in current:
            raise ValueError("planned exemplar no longer exists")
        _, exemplar = current[task.scenario_id]
        request = requests_for(checks[exemplar["check_id"]], exemplar).get((task.role, task.turn))
        if task.model_id != exemplar["check_id"] or request != task.request:
            raise ValueError("exemplar changed since planning")
    answers = run_questions(bundle, max_cost_usd=max_cost_usd, client=client)
    by_directory = {d: _answer_index(_read_jsonl(d / ANSWERS)) for d in examples}
    for answer in answers:
        if answer.error is None:
            directory, _ = current[answer.scenario_id]
            by_directory[directory][answer.scenario_id, answer.role, answer.turn] = {
                "id": answer.scenario_id, "role": answer.role, "turn": answer.turn,
                "input_sha256": answer.input_sha256, "model": answer.judge.model,
                "answers": {key: value.model_dump(mode="json") for key, value in answer.answers.items()},
            }
    for directory, rows in by_directory.items():
        if not rows:
            continue
        path = directory / ANSWERS
        temporary = path.with_suffix(".tmp")
        temporary.write_text("".join(json.dumps(rows[key], ensure_ascii=False, sort_keys=True) + "\n" for key in sorted(rows)))
        temporary.replace(path)
    return {"requests": len(plan.tasks), "cost_usd": sum(a.cost_usd for a in answers)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["verify", "plan", "refresh"], nargs="?", default="verify")
    parser.add_argument("--root", type=Path, default=CHECKS_DIR)
    parser.add_argument("--only")
    parser.add_argument("--model", default=DEFAULT_JUDGE_MODEL)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--max-cost-usd", type=float)
    args = parser.parse_args()
    checks = load_checks(args.root)
    if args.command == "plan":
        if args.output is None:
            parser.error("plan requires --output results/<UTC-run-id>")
        plan = plan_refresh(args.root, checks, args.output, model=args.model, only=args.only)
        print(plan.model_dump_json(indent=2) if plan else "No stale or missing answers.")
        return 0
    if args.command == "refresh":
        if args.plan is None or args.plan.name != PLAN_FILE or args.max_cost_usd is None:
            parser.error("refresh requires --plan <bundle>/scan_plan.json and --max-cost-usd")
        print(refresh(args.root, checks, args.plan.parent, max_cost_usd=args.max_cost_usd))
    failures, totals = verify(args.root, checks, Thresholds(), model=args.model)
    print(*failures, sep="\n")
    print(totals)
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
