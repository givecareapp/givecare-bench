#!/usr/bin/env python3
"""Run one check against one transcript with the judge model and print the trace.

An authoring tool. It spends a fraction of a cent per transcript and writes
nothing. Use it to see each turn's probabilities and the verdict the rule
derives before committing a check definition.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invisiblebench.api.typesafe import DEFAULT_JUDGE_MODEL, SystemOneClient  # noqa: E402
from invisiblebench.evaluation.check_registry import CHECKS_DIR, load_check  # noqa: E402
from invisiblebench.evaluation.rules import (  # noqa: E402
    build_request,
    derive,
    request_turns,
)
from invisiblebench.models.scan import JudgeSettings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check_id")
    parser.add_argument("transcripts", nargs="+", type=Path, help="transcript .jsonl files")
    parser.add_argument("--model", default=DEFAULT_JUDGE_MODEL)
    args = parser.parse_args()
    paths = list(CHECKS_DIR.rglob(f"{args.check_id}.yaml"))
    if len(paths) != 1:
        print(f"unknown check: {args.check_id}", file=sys.stderr)
        return 2
    check = load_check(paths[0])
    settings = JudgeSettings(model=args.model)
    client = SystemOneClient()
    for path in args.transcripts:
        transcript = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        answers = {}
        print(f"== {path.name}")
        for role, turn in request_turns(transcript):
            request = build_request([check], transcript, role, turn)
            if not request["questions"]:
                continue
            result = client.ask(model=args.model, state=request["state"], questions=request["questions"])
            answers[(role, turn)] = result["nouls"]
            trace = ", ".join(f"{k.split('/')[-1]} {v:.2f}" for k, v in result["nouls"].items())
            print(f"  {role} {turn}: {trace}")
        judgment = derive(
            check, transcript, answers, settings.thresholds,
            model_id="probe", scenario_id=path.stem, plan_sha256="0" * 64,
        )
        print(f"  -> {judgment.verdict.value}: {judgment.rationale}")
        for span in judgment.evidence:
            print(f"     {span.role} turn {span.turn}: {span.quote[:120]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
