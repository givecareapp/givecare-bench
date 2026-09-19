#!/usr/bin/env python3
"""Verify every check against its exemplars from committed judge answers.

Each dimension directory holds `examples.jsonl`: short transcripts with the
verdict the check must derive. Beside it, `examples.answers.jsonl` holds the
judge model's saved probabilities for each exemplar turn, bound to the request
hash. `verify` derives verdicts from those committed answers with no network
and fails on a mismatch, a stale answer (the check or exemplar changed), or a
check with no exemplars. `refresh` asks the judge for the stale or missing
rows only and rewrites the answers file. Exemplars ask one check's questions
alone, so editing another check never stales them.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invisiblebench.api.client import cost_tracker  # noqa: E402
from invisiblebench.api.typesafe import DEFAULT_JUDGE_MODEL  # noqa: E402
from invisiblebench.evaluation import rules  # noqa: E402
from invisiblebench.evaluation.check_registry import CHECKS_DIR, load_checks  # noqa: E402
from invisiblebench.models.scan import Check, MemoryContext, Thresholds, Verdict  # noqa: E402

EXAMPLES = "examples.jsonl"
ANSWERS = "examples.answers.jsonl"
VERDICTS = {verdict.value for verdict in Verdict}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))


def dimension_dirs(root: Path) -> list[Path]:
    return sorted(path for path in root.glob("*/*") if path.is_dir())


def load_examples(root: Path, checks: dict[str, Check]) -> dict[Path, list[dict[str, Any]]]:
    """Exemplars per dimension directory, validated against the registry."""
    found: dict[Path, list[dict[str, Any]]] = {}
    seen: set[str] = set()
    for directory in dimension_dirs(root):
        rows = _read_jsonl(directory / EXAMPLES)
        for row in rows:
            for field in ("id", "check_id", "expected", "transcript"):
                if field not in row:
                    raise ValueError(f"{directory / EXAMPLES}: exemplar missing {field}")
            if row["id"] in seen:
                raise ValueError(f"duplicate exemplar id: {row['id']}")
            seen.add(row["id"])
            if row["check_id"] not in checks:
                raise ValueError(f"{row['id']}: unknown check {row['check_id']}")
            if checks[row["check_id"]].dimension != directory.name:
                raise ValueError(f"{row['id']}: belongs in {checks[row['check_id']].dimension}/")
            if row["expected"] not in VERDICTS:
                raise ValueError(f"{row['id']}: expected must be one of {sorted(VERDICTS)}")
            if not any(turn.get("role") == "assistant" for turn in row["transcript"]):
                raise ValueError(f"{row['id']}: transcript needs an assistant turn")
        found[directory] = rows
    return found


def requests_for(check: Check, exemplar: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    memory = MemoryContext(persistent_memory=bool(exemplar.get("memory_declared", False)))
    requests = {}
    for role, turn in rules.request_turns(exemplar["transcript"]):
        request = rules.build_request([check], exemplar["transcript"], role, turn, memory)
        if request["questions"]:
            requests[(role, turn)] = request
    return requests


def _answer_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str, int], dict[str, Any]]:
    return {(row["id"], row["role"], row["turn"]): row for row in rows}


def verify(
    root: Path, checks: dict[str, Check], thresholds: Thresholds
) -> tuple[list[str], dict[str, int]]:
    """Return failure lines and a summary. Never calls the judge."""
    failures: list[str] = []
    totals = {"exemplars": 0, "passed": 0, "mismatch": 0, "stale": 0, "uncovered": 0}
    covered: dict[str, set[str]] = defaultdict(set)
    for directory, exemplars in load_examples(root, checks).items():
        answers = _answer_index(_read_jsonl(directory / ANSWERS))
        for exemplar in exemplars:
            totals["exemplars"] += 1
            check = checks[exemplar["check_id"]]
            saved: dict[tuple[str, int], dict[str, float]] = {}
            stale = False
            for (role, turn), request in requests_for(check, exemplar).items():
                row = answers.get((exemplar["id"], role, turn))
                if row is None or row["input_sha256"] != rules.input_hash(request):
                    stale = True
                    break
                saved[(role, turn)] = row["nouls"]
            if stale:
                totals["stale"] += 1
                failures.append(f"STALE    {exemplar['id']}: run `check_examples.py refresh`")
                continue
            judgment = rules.derive(
                check,
                exemplar["transcript"],
                saved,
                thresholds,
                model_id="exemplar",
                scenario_id=exemplar["id"],
                plan_sha256="0" * 64,
                memory_declared=bool(exemplar.get("memory_declared", False)),
            )
            covered[check.id].add(exemplar["expected"])
            if judgment.verdict.value == exemplar["expected"]:
                totals["passed"] += 1
            else:
                totals["mismatch"] += 1
                failures.append(
                    f"MISMATCH {exemplar['id']}: expected {exemplar['expected']}, "
                    f"derived {judgment.verdict.value}: {judgment.rationale}"
                )
    for check_id in sorted(checks):
        expected = covered.get(check_id, set())
        if "FAIL" not in expected or not (expected & {"PASS", "NOT_APPLICABLE"}):
            totals["uncovered"] += 1
            failures.append(
                f"UNCOVERED {check_id}: needs one FAIL exemplar and one PASS or NOT_APPLICABLE exemplar"
            )
    return failures, totals


def refresh(
    root: Path, checks: dict[str, Check], *, client: Any, model: str, only: str | None = None
) -> dict[str, int]:
    """Ask the judge for stale or missing exemplar answers; rewrite each answers file."""
    totals = {"asked": 0, "kept": 0}
    for directory, exemplars in load_examples(root, checks).items():
        if not exemplars:
            continue  # nothing to answer; leave the directory untouched
        path = directory / ANSWERS
        existing = _answer_index(_read_jsonl(path))
        fresh: list[dict[str, Any]] = []
        for exemplar in exemplars:
            check = checks[exemplar["check_id"]]
            for (role, turn), request in requests_for(check, exemplar).items():
                digest = rules.input_hash(request)
                row = existing.get((exemplar["id"], role, turn))
                if row is not None and row["input_sha256"] == digest and (
                    only is None or check.id != only
                ):
                    fresh.append(row)
                    totals["kept"] += 1
                    continue
                if only is not None and check.id != only:
                    if row is not None:
                        fresh.append(row)
                    continue
                result = client.ask(model=model, state=request["state"], questions=request["questions"])
                totals["asked"] += 1
                fresh.append(
                    {
                        "id": exemplar["id"],
                        "role": role,
                        "turn": turn,
                        "input_sha256": digest,
                        "model": result["model"],
                        "nouls": result["nouls"],
                    }
                )
        fresh.sort(key=lambda row: (row["id"], row["role"], row["turn"]))
        _write_jsonl(path, fresh)
    return totals


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="verify", choices=["verify", "refresh"])
    parser.add_argument("--root", type=Path, default=CHECKS_DIR)
    parser.add_argument("--only", help="refresh: one check id")
    parser.add_argument("--model", default=DEFAULT_JUDGE_MODEL)
    args = parser.parse_args()
    checks = load_checks(args.root)
    thresholds = Thresholds()
    try:
        if args.command == "refresh":
            from invisiblebench.api.typesafe import SystemOneClient

            totals = refresh(args.root, checks, client=SystemOneClient(), model=args.model, only=args.only)
            print(
                f"asked {totals['asked']} requests, kept {totals['kept']}; "
                f"cost ${cost_tracker.total:.4f}"
            )
        failures, totals = verify(args.root, checks, thresholds)
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for line in failures:
        print(line)
    print(
        f"exemplars {totals['exemplars']}: passed {totals['passed']}, mismatch {totals['mismatch']}, "
        f"stale {totals['stale']}; uncovered checks {totals['uncovered']}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
