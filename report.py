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
            "family": summary["family"],
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


def diff_reports(before: dict, after: dict) -> dict:
    """Verdict-for-verdict comparison of two judge logs over the same samples."""
    if before["kind"] != after["kind"]:
        raise ValueError("Compare two control reports or two target reports, not one of each")
    trials = lambda report: {(t["sample_id"], t["epoch"]): t for t in report["trials"]}  # noqa: E731
    first, second = trials(before), trials(after)
    shared = sorted(set(first) & set(second))
    flips = [
        {"sample_id": key[0], "epoch": key[1], "check": first[key]["check"],
         "turn": first[key]["turn"], "reference": first[key]["reference"],
         "before": first[key]["verdict"], "after": second[key]["verdict"]}
        for key in shared if first[key]["verdict"] != second[key]["verdict"]
    ]
    counts = {}
    for flip in flips:
        label = f"{flip['before']}->{flip['after']}"
        counts[label] = counts.get(label, 0) + 1
    identity = lambda report: {  # noqa: E731
        "eval_id": report["run"]["eval_id"], "model": report["run"]["model"],
        "git_commit": report["summary"].get("git_commit"),
        "source_sha256": report["summary"].get("source_sha256"),
    }
    return {
        "kind": "verdict-diff", "before": identity(before), "after": identity(after),
        "paired": len(shared), "only_before": len(set(first) - set(second)),
        "only_after": len(set(second) - set(first)), "flip_counts": dict(sorted(counts.items())),
        "flips": flips,
    }


def _disagreement(reference: str, verdict: str) -> str:
    if reference == "FAIL" and verdict == "PASS":
        return "False pass"
    if reference == "PASS" and verdict == "FAIL":
        return "False fail"
    if "UNCLEAR" in (reference, verdict):
        return "Unclear disagreement"
    if (reference == "NOT_APPLICABLE") != (verdict == "NOT_APPLICABLE"):
        return "Applicability disagreement"
    return "Disagreement"


def _finding_lines(trial: dict) -> list[str]:
    evidence = trial["evidence"] or {}
    return [
        f"Inspect sample: `{trial['sample_id']}` (epoch {trial['epoch']}).",
        f"Reason: {json.dumps(evidence.get('reason', 'No judge reason recorded.'), ensure_ascii=False)}",
        f"Response evidence: {json.dumps(evidence.get('response_quote', 'Missing.'), ensure_ascii=False)}",
        f"User cue (turn {evidence.get('cue_turn', '?')}): "
        f"{json.dumps(evidence.get('cue_quote', 'Missing.'), ensure_ascii=False)}",
        "",
    ]


def render_markdown(report: dict) -> str:
    """Human reading layer; the Inspect log remains the evidence record."""
    run = report["run"]
    summary = report["summary"]
    control = report["kind"] == "judge-development-audit"
    lines = [
        "# InvisibleBench evaluation report",
        "",
        f"**Use:** {report['kind']}  ",
        f"**Family:** {run['family']}  ",
        f"**Status:** {summary['status']}  ",
        f"**Judge model:** {run['model']}  ",
        f"**Development version:** {run['benchmark_version']}  ",
        f"**Validation:** {report['validation']}",
        "",
    ]
    if control:
        lines.extend([
            "## Judge output against authored labels",
            "",
            "| Layer | Check | Planned | Ref PASS | Ref FAIL | Ref UNCLEAR | Ref N/A | Exact "
            "| False pass | False fail | Applicability | Judge UNCLEAR | Missing | Error | Unscored |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ])
        for layer, checks in summary["by_layer"].items():
            for check, counts in checks.items():
                ref = counts["reference_counts"]
                lines.append(
                    f"| {layer} | `{check}` | {counts['planned']} | {ref.get('PASS', 0)} | "
                    f"{ref.get('FAIL', 0)} | {ref.get('UNCLEAR', 0)} | {ref.get('NOT_APPLICABLE', 0)} | "
                    f"{counts['exact_match']} | {counts['false_pass']} | {counts['false_fail']} | "
                    f"{counts['applicability_error']} | {counts['unclear']} | {counts['missing']} | "
                    f"{counts['execution_error']} | {counts['unscored']} |"
                )
        lines.extend([
            "",
            "Control counts compare judge output with authored development labels. A false pass "
            "is a reference FAIL judged PASS; a false fail is a reference PASS judged FAIL. These "
            "are development controls; they do not estimate precision or recall on independent cases.",
            "",
            "### Confusion by check (reference → judge)",
            "",
        ])
        for checks in summary["by_layer"].values():
            for check, counts in checks.items():
                cells = [
                    f"{expected}→{predicted} {n}"
                    for expected, row in sorted(counts["confusion"].items())
                    for predicted, n in sorted(row.items()) if n
                ]
                lines.append(f"- `{check}`: " + (" · ".join(cells) if cells else "no scored items"))
    else:
        lines.extend([
            "## Per-check observations",
            "",
            "| Layer | Check | Planned | PASS | FAIL | UNCLEAR | N/A | Interrupted | Unattempted "
            "| Judge missing | Judge error | Unscored |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ])
        for layer, checks in summary["by_layer"].items():
            for check, counts in checks.items():
                lines.append(
                    f"| {layer} | `{check}` | {counts['planned']} | {counts['PASS']} | "
                    f"{counts['FAIL']} | {counts['UNCLEAR']} | {counts['NOT_APPLICABLE']} | "
                    f"{counts['generation_interrupted']} | {counts['generation_unattempted']} | "
                    f"{counts['judge_missing']} | {counts['execution_error']} | {counts['unscored']} |"
                )
        source = summary["target"]
        lines.extend([
            "",
            "The counts describe unvalidated judge output, not model quality. Interrupted and "
            "unattempted opportunities come from the generation log; the judge columns describe "
            "this judging run.",
            "",
            "## Source generation",
            "",
            f"- Inspect evaluation ID: `{source['eval_id']}`; model: `{source['model']}`.",
            f"- Source log SHA-256: `{source['source_log_sha256']}`.",
            f"- Conversations: {source['complete_samples']} complete, "
            f"{source['interrupted_samples']} interrupted, of {source['planned_samples']} planned.",
        ])
        for conversation in source["conversations"]:
            if conversation["status"] == "complete":
                continue
            line = (f"- `{conversation['sample_id']}` (epoch {conversation['epoch']}): "
                    f"{conversation['status']}, {conversation['completed_turns']} of "
                    f"{conversation['planned_turns']} turns completed")
            if conversation["error"]:
                line += f"; error: {json.dumps(conversation['error'], ensure_ascii=False)}"
            lines.append(line)
    if control:
        lines.extend(["", "## Judge disagreements requiring review", ""])
        findings = [t for t in report["trials"]
                    if t["verdict"] is not None and t["verdict"] != t["reference"]]
        if not findings:
            lines.append("No disagreements with authored labels among scored items. "
                         "Check missing, error, and unscored coverage above.")
        for trial in findings:
            kind = _disagreement(trial["reference"], trial["verdict"])
            lines.extend([
                f"### {kind}: {trial['layer']} / {trial['check']} / turn {trial['turn']}",
                "",
                f"Reference {trial['reference']}; judge {trial['verdict']}.",
                *_finding_lines(trial),
            ])
    else:
        lines.extend(["", "## Findings requiring review", ""])
        findings = [t for t in report["trials"] if t["verdict"] in {"FAIL", "UNCLEAR"}]
        if not findings:
            lines.append("No recorded FAIL or UNCLEAR verdicts. Check interrupted, unattempted, "
                         "and unscored coverage above.")
        for trial in findings:
            lines.extend([
                f"### {trial['verdict']}: {trial['layer']} / {trial['check']} / turn {trial['turn']}",
                "",
                *_finding_lines(trial),
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
    parser.add_argument("--diff", metavar="EARLIER_LOG",
                        help="Print the verdict-for-verdict diff from this earlier judge log to LOG")
    args = parser.parse_args()
    report = build_report(read_eval_log(args.log))
    if args.diff:
        diff = diff_reports(build_report(read_eval_log(args.diff)), report)
        print(json.dumps(diff, indent=2, ensure_ascii=False, default=str))
        return
    if args.format == "markdown":
        print(render_markdown(report), end="")
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
