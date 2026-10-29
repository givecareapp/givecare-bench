"""Offline audit reports from saved Inspect judge logs."""

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
            "log_location": log.location,
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


def render_markdown(report: dict) -> str:
    """Human reading layer; the Inspect log remains the evidence record."""
    run = report["run"]
    summary = report["summary"]
    lines = [
        "# InvisibleBench evaluation report",
        "",
        f"**Use:** {report['kind']}  ",
        f"**Status:** {summary['status']}  ",
        f"**Judge model:** {run['model']}  ",
        f"**Development version:** {run['benchmark_version']}  ",
        f"**Validation:** {report['validation']}",
        "",
        "## Per-check observations",
        "",
        "| Layer | Check | Planned | PASS | FAIL | UNCLEAR | N/A | Missing | Error | Unscored |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for layer, checks in summary["by_layer"].items():
        for check, counts in checks.items():
            verdicts = (
                {verdict: sum(row.get(verdict, 0) for row in counts["confusion"].values())
                 for verdict in VERDICTS}
                if "confusion" in counts else counts
            )
            lines.append(
                f"| {layer} | `{check}` | {counts['planned']} | "
                f"{verdicts['PASS']} | {verdicts['FAIL']} | "
                f"{verdicts['UNCLEAR']} | {verdicts['NOT_APPLICABLE']} | {counts['missing']} | "
                f"{counts['execution_error']} | {counts['unscored']} |"
            )
    lines.extend(["", "The counts describe unvalidated judge output, not model quality."
                  if report["kind"] == "target-judging-audit"
                  else "Control counts compare judge output with authored development labels."])
    if report["kind"] == "target-judging-audit":
        source = summary["target"]
        lines.extend(["", "## Source generation", "",
                      f"- Inspect evaluation ID: `{source['eval_id']}`; model: `{source['model']}`.",
                      f"- Source log SHA-256: `{source['source_log_sha256']}`.",
                      f"- Conversations: {source['complete_samples']} complete of "
                      f"{source['planned_samples']} planned.",
                      "- Per-check missing counts include absent generation and judge opportunities."])
    lines.extend(["", "## Findings requiring review", ""])
    findings = [t for t in report["trials"] if t["verdict"] in {"FAIL", "UNCLEAR"}]
    if not findings:
        lines.append("No recorded FAIL or UNCLEAR verdicts. Check missing and unscored coverage above.")
    for trial in findings:
        evidence = trial["evidence"] or {}
        lines.extend([
            f"### {trial['verdict']}: {trial['layer']} / {trial['check']} / turn {trial['turn']}",
            "",
            f"Inspect sample: `{trial['sample_id']}` (epoch {trial['epoch']}).",
            f"Reason: {json.dumps(evidence.get('reason', 'No judge reason recorded.'), ensure_ascii=False)}",
            f"Response evidence: {json.dumps(evidence.get('response_quote', 'Missing.'), ensure_ascii=False)}",
            f"User cue (turn {evidence.get('cue_turn', '?')}): "
            f"{json.dumps(evidence.get('cue_quote', 'Missing.'), ensure_ascii=False)}",
            "",
        ])
    plan = run["plan"] or {}
    plan_config = plan.get("config") or {}
    lines.extend(["", "## Provenance and limits", "",
                  f"- Judge evaluation ID: `{run['eval_id']}`.",
                  f"- Native Inspect log: `{run['log_location']}`. Open it with `inspect view` and select the sample IDs above.",
                  f"- Source hashes: `{json.dumps(summary['source_sha256'], sort_keys=True)}`.",
                  f"- Inspect task: `{run['task']}`; epochs: {summary['epochs']}.",
                  f"- Effective plan settings: `{json.dumps(plan_config, sort_keys=True)}`.",
                  f"- Usage and reported cost: `{json.dumps(run['model_usage'], sort_keys=True)}`.",
                  "- Mock runs establish plumbing only. No independent human or clinician validation is claimed.",
                  "- Inspect logs contain the complete transcripts, settings, and per-sample records; review them before sharing this report."])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", help="Saved Inspect .eval judge-development log")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    report = build_report(read_eval_log(args.log))
    if args.format == "markdown":
        print(render_markdown(report), end="")
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
