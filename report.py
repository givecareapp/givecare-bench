"""Offline audit report for a saved Inspect judge-development log."""

import argparse
import json

from inspect_ai.log import EvalLog, read_eval_log

from grader import VERDICTS, summarize, summarize_target


def build_report(log: EvalLog) -> dict:
    use = (log.eval.metadata or {}).get("use")
    summary = summarize_target(log) if use == "target-judging" else summarize(log)
    trials = []
    for sample in log.samples or []:
        scores = list((sample.scores or {}).values())
        score = scores[0] if len(scores) == 1 else None
        verdict = score.value if score and isinstance(score.value, str) and score.value in VERDICTS else None
        trials.append({
            "sample_id": str(sample.id),
            "epoch": sample.epoch,
            "check": sample.metadata["check"],
            "layer": sample.metadata["layer"],
            "turn": sample.metadata["turn"],
            "source_sample": sample.metadata.get("source_sample"),
            "source_epoch": sample.metadata.get("source_epoch"),
            "reference": sample.target if use == "judge-development" else None,
            "verdict": verdict,
            "evidence": score.metadata.get("evidence") if score and score.metadata else None,
            "unscored_reason": score.explanation if score and verdict is None else None,
            "execution_error": sample.error.model_dump(mode="json") if sample.error else None,
        })
    return {
        "kind": f"{use}-audit",
        "validation": "development rubric; no independent human validation",
        "summary": summary,
        "run": {
            "eval_id": log.eval.eval_id,
            "created": log.eval.created,
            "task": log.eval.task,
            "model": log.eval.model,
            "benchmark_version": log.eval.metadata["benchmark_version"],
            "versions": log.eval.model_dump(mode="json", include={
                "task_version", "revision", "packages"}),
            "model_generate_config": log.eval.model_generate_config.model_dump(mode="json")
            if log.eval.model_generate_config else None,
            "config": log.eval.config.model_dump(mode="json"),
            "plan": log.plan.model_dump(mode="json") if log.plan else None,
            "model_usage": {name: usage.model_dump(mode="json")
                            for name, usage in (log.stats.model_usage or {}).items()}
            if log.stats else {},
        },
        "trials": sorted(trials, key=lambda row: (row["sample_id"], row["epoch"])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", help="Saved Inspect .eval judge-development log")
    args = parser.parse_args()
    print(json.dumps(build_report(read_eval_log(args.log)), indent=2, ensure_ascii=False,
                     default=str))


if __name__ == "__main__":
    main()
