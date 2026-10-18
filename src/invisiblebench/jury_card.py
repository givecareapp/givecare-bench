"""Render a run's Jury Card from its saved judgments, without model calls."""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from invisiblebench.judge import (
    ANSWERS_FILE,
    LEDGER_FILE,
    PLAN_FILE,
    load_scan,
    sha256,
)
from invisiblebench.models.scan import Judgment, ScanPlan, Verdict
from invisiblebench.scoring import MIN_CHECK_CASES, build_scorecard, unresolved_outcomes
from invisiblebench.utils.manifest import run_timestamp
from invisiblebench.validation import validation_agreement

CARD_FILE = "jury-card.md"
COMMENTARY_MARKER = "<!-- jury-card:commentary -->"


def _cell(value: object) -> str:
    return html.escape(str(value)).replace("|", "&#124;").replace("\n", "<br>")


def _range(span: list[float] | None) -> str:
    if span is None:
        return "n/a"
    low, high = span
    return f"{low:.0%}" if low == high else f"{low:.0%}–{high:.0%}"


def _link(label: str, path: str) -> str:
    return f"[{_cell(label)}]({quote(path, safe='/#')})"


def _validation_lines(bundle: Path, plan: ScanPlan, records: list[Judgment]) -> list[str]:
    lines = [
        "## Validation evidence",
        "",
        "Replay shows how a verdict arose. Correctness needs separate evidence. "
        "Agreement with controlled fixtures tests the declared requirements. "
        "These cases do not measure population accuracy or clinical safety.",
        "",
    ]
    try:
        report = validation_agreement(bundle, plan, records)
    except ValueError as exc:
        return lines + [
            f"**Validation evidence rejected:** {_cell(exc)}. Verdicts are unchanged.", ""
        ]
    if report is None:
        return []
    bases = Counter(row["basis"] for row in report["rows"])
    lines.extend(
        [
            "Expectations are frozen in the source summaries bound by this plan. "
            "They are excluded from judge requests and verdict rules. "
            "Authorship is reported; independence is not authenticated.",
            "",
            f"- Labeled judgments: {report['labeled_judgments']}; "
            f"unlabeled judgments: {report['unlabeled_judgments']}.",
            f"- Labeled checks: {len(report['labeled_checks'])}/{len(plan.checks)}.",
            f"- Differences from expectation: {report['mismatches']}/{report['labeled_judgments']} "
            "labeled judgments, including UNCLEAR and applicability differences.",
            f"- Evidence basis: "
            f"{_cell('; '.join(f'{key}: {count}' for key, count in sorted(bases.items())))}.",
            f"- False passes: {report['false_pass']} (expected FAIL, observed PASS).",
            f"- False failures: {report['false_fail']} (expected PASS, observed FAIL).",
            f"- Unresolved labeled judgments: {report['unresolved']} (observed UNCLEAR).",
            "- Applicability errors and all other differences remain visible in the case table. "
            "Unlabeled checks have no correctness claim.",
            "",
            "| Case / check | Expected | Observed | Basis and reason |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in report["rows"]:
        lines.append(
            f"| {_cell(row['model_id'])} / {_cell(row['scenario_id'])}<br>{_cell(row['check_id'])} "
            f"| {row['expected']} | {row['observed']} "
            f"| {_cell(row['basis'])}<br>{_cell(row['reason'])}<br>"
            f"Author: {_cell(row['author'])}; source: {_cell(row['source'])} |"
        )
    return lines + [""]


def write_jury_card(bundle: Path) -> Path:
    """Write one Markdown report. Retain its commentary only for the same evidence."""
    bundle = Path(bundle)
    plan, answers, records = load_scan(bundle, complete=True)
    scorecard = build_scorecard(bundle)
    plan_hash = sha256((bundle / PLAN_FILE).read_bytes())
    answers_hash = sha256((bundle / ANSWERS_FILE).read_bytes())
    ledger_hash = sha256((bundle / LEDGER_FILE).read_bytes())
    binding = f"<!-- jury-card:v2 plan={plan_hash} answers={answers_hash} judgments={ledger_hash} -->"
    output = bundle / CARD_FILE
    commentary = "\nNo added commentary.\n"
    if output.exists():
        saved = output.read_text()
        if binding not in saved or saved.count(COMMENTARY_MARKER) != 1:
            raise ValueError("existing Jury Card does not match this evidence or its commentary marker")
        commentary = saved.split(COMMENTARY_MARKER, 1)[1]

    sources = [
        (
            source,
            json.loads((bundle / source.manifest.path).read_bytes()),
            json.loads((bundle / source.summary.path).read_bytes()),
        )
        for source in plan.sources
    ]
    first_attempts = {}
    for answer in answers:
        first_attempts.setdefault(answer.key, answer)
    first_valid = sum(answer.error is None for answer in first_attempts.values())
    errors = Counter(answer.error for answer in answers if answer.error)
    judges = sorted({answer.judge.model or "not recorded" for answer in answers})
    generation_costs = [summary.get("actual_cost_usd") for _, _, summary in sources]
    generation_cost = (
        sum(generation_costs) if all(value is not None for value in generation_costs) else None
    )
    judge_cost = sum(answer.cost_usd for answer in answers)
    timestamp = run_timestamp(bundle, [manifest for _, manifest, _ in sources])
    date_label = f"{timestamp.day} {timestamp:%b %Y, %H:%M:%S} UTC" if timestamp else bundle.name
    models = scorecard["models"]
    model_label = models[0]["model"] if len(models) == 1 else f"{len(models)} models"
    validation_lines = _validation_lines(bundle, plan, records)
    no_frozen_expectations = not validation_lines
    lines = [
        f"# {_cell(model_label)} — {_cell(date_label)}", "", binding, "",
        "**Jury Card · MODEL-JUDGED. Care remains directional.** This card describes the recorded run. "
        "It does not establish clinical outcomes, general model quality, or judge accuracy.", "",
        *(["**Product development scan.** Supplemental checks are included; this scan is not eligible "
           "for public benchmark projection.", ""] if plan.supplemental_checks else []),
        f"{len(plan.transcripts)} conversations · {len(plan.checks)} checks per conversation · "
        f"Benchmark {_cell(plan.benchmark_version)}.", "",
        *(["No frozen research expectations are attached; correctness is not measured by this card.", ""]
          if no_frozen_expectations else []),
        "## Findings", "",
        "Each row counts conversations. PASS is limited to that check; UNCLEAR is unresolved; "
        "NOT_APPLICABLE means the check did not apply.", "",
    ]
    checks = {check.id: check for check in plan.checks}
    outcomes = unresolved_outcomes(bundle, plan, records)
    refs = {(ref.model_id, ref.scenario_id): ref for ref in plan.transcripts}
    row_numbers = {record.key: i for i, record in enumerate(records, 1)}
    for model in scorecard["models"]:
        model_records = [record for record in records if record.model_id == model["model_id"]]
        settled_counts = Counter(
            record.check_id
            for record in model_records
            if record.verdict in (Verdict.PASS, Verdict.FAIL)
        )
        lines.extend([f"### {_cell(model['model'])}", ""])
        for layer in ("safety", "care"):
            layer_check_ids = [check.id for check in plan.checks if check.layer == layer]
            covered = sum(settled_counts[check_id] >= MIN_CHECK_CASES for check_id in layer_check_ids)
            none = sum(settled_counts[check_id] == 0 for check_id in layer_check_ids)
            none_label = "check has" if none == 1 else "checks have"
            lines.extend([
                f"#### {layer.title()}", "",
                f"Coverage: {covered}/{len(layer_check_ids)} checks have at least {MIN_CHECK_CASES} "
                f"settled PASS/FAIL cases; {none} {none_label} none. This is coverage, not accuracy.", "",
            ])
            for dimension in model[layer]:
                check_ids = [check.id for check in plan.checks
                             if check.layer == layer and check.dimension == dimension]
                if not check_ids:
                    continue
                lines.extend([f"**{_cell(dimension)}**", "",
                    "| Check | PASS | FAIL | UNCLEAR | NOT_APPLICABLE |",
                    "| --- | ---: | ---: | ---: | ---: |"])
                for check_id in check_ids:
                    check = checks[check_id]
                    judged = [r for r in records if r.model_id == model["model_id"]
                              and r.check_id == check_id]
                    tally = Counter(r.verdict for r in judged)
                    c = {verdict.value: tally[verdict] for verdict in Verdict}
                    label = check.name.replace("_", " ")
                    dyad = " · caregiver–recipient" if check.dyad else ""
                    lines.append(f"| {_cell(label)}{dyad} (`{_cell(check_id)}`) | {c['PASS']} | {c['FAIL']} "
                                 f"| {c['UNCLEAR']} | {c['NOT_APPLICABLE']} |")
                lines.extend(["", f"<details><summary>{layer.title()} / {_cell(dimension)}: "
                              f"scope and evidence for {len(check_ids)} checks</summary>", ""])
                for check_id in check_ids:
                    check = checks[check_id]
                    label = check.name.replace("_", " ")
                    flagged = [r for r in records if r.model_id == model["model_id"]
                               and r.check_id == check_id and r.verdict in {Verdict.FAIL, Verdict.UNCLEAR}]
                    lines.extend([f"##### {_cell(label)} (`{_cell(check_id)}`)", "",
                        f"{_cell(check.summary)} **PASS means:** {_cell(check.pass_meaning)} "
                        f"(basis: {_cell(check.basis)}). Frozen definition: {_link('scan plan', PLAN_FILE)}.", ""])
                    if not flagged:
                        lines.append(f"No FAIL or UNCLEAR judgments. See the full {_link('judgments ledger', LEDGER_FILE)} and frozen source index in the scan plan.")
                    for record in flagged:
                        ref = refs[record.model_id, record.scenario_id]
                        evidence = "<br>".join(
                            f"{span.role} turn {span.turn}: “{_cell(span.quote)}”" for span in record.evidence
                        ) or "No quote supplied."
                        result = f"**{record.verdict.value}** — {_cell(record.rationale)}"
                        if record.key in outcomes:
                            result += ". Possible outcomes: " + ", ".join(
                                sorted(value.value for value in outcomes[record.key])
                            )
                        lines.append(f"- {_link(record.scenario_id, ref.path)}: {evidence} — {result}; "
                                     f"{_link(f'ledger row {row_numbers[record.key]}', f'{LEDGER_FILE}#L{row_numbers[record.key]}')}.")
                    lines.append("")
                lines.extend(["</details>", ""])
                lines.append("")
    lines.extend([
        "<details><summary>Method and run records</summary>", "",
        "## Score details", "",
        "Safety shows the failure-rate range; Care shows the pass-rate range. A range shows the lowest and highest rate allowed by unresolved verdicts; it is not a confidence interval or a bound on real-world harm. Safety averages eligible checks equally, with at least "
        f"{MIN_CHECK_CASES} settled cases per check. Care rates remain directional. No combined score is calculated.", "",
    ])
    for model in scorecard["models"]:
        lines.extend([f"### {_cell(model['model'])}", "",
                      "| Layer | Dimension | Rate and meaning | Conversations with settled FAIL |",
                      "| --- | --- | ---: | ---: |"])
        for layer in ("safety", "care"):
            for dimension, observation in model[layer].items():
                span = observation["failure_rate_range"] if layer == "safety" else observation["pass_rate_range"]
                rate = f"{_range(span)} {'failure rate' if layer == 'safety' else 'pass rate'}"
                failed = (f"{observation['failed_scenarios']}/{observation['settled_scenarios']}"
                          if layer == "safety" else "—")
                lines.append(f"| {layer.title()} | {_cell(dimension)} | {rate} | {failed} |")
        lines.append("")
    lines.extend([
        "## Run details", "",
        "- Model ID(s): " + "; ".join(_cell(m["model_id"]) for m in scorecard["models"]) +
        f"; benchmark { _cell(plan.benchmark_version) }; engine {_cell(plan.engine_version)}.",
        f"- Judge: {_cell(plan.judge.model)}; thresholds: no at or below {plan.judge.thresholds.low:g}, "
        f"yes at or above {plan.judge.thresholds.high:g}.",
        f"- Completed requests: {sum(a.error is None for a in answers)}; derived judgments: {len(records)}.",
        f"- Valid first attempts: {first_valid}/{len(first_attempts)} (answer acceptance, not accuracy).",
        f"- Technical attempts: {sum(errors.values())}. " + "; ".join(
            f"{_cell(k)}: {v}" for k, v in sorted(errors.items())),
        f"- Returned judge model: {_cell('; '.join(judges))}; request cost: ${judge_cost:.8f}.",
        f"- Source generation cost: {'not recorded' if generation_cost is None else f'${generation_cost:.8f}'}; "
        "cost and elapsed time describe complete source runs, including unselected conversations.", "",
        *([f"- Total recorded cost: **${generation_cost + judge_cost:.8f}**.", ""]
          if generation_cost is not None else []),
        "Source hashes, quote provenance, decision binding, and plan coverage were checked when generated.", "",
    ])
    if not no_frozen_expectations:
        lines.extend(validation_lines)
    lines.extend(["", "## Source records", ""])
    for source, manifest, summary in sources:
        policy = manifest.get("transcript_policy") or {}
        lines.extend([
            f"- Source run: `{_cell(manifest['run_id'])}`; {_cell(manifest.get('run_date', 'date not recorded'))}.",
            f"- {_link('Manifest and generation settings', source.manifest.path)} · "
            f"{_link('Run summary', source.summary.path)}.",
            f"- Harness: {_cell(manifest.get('harness', 'not recorded'))} / "
            f"{_cell(manifest.get('mode', 'not recorded'))}; "
            f"persistent memory: {'declared' if policy.get('persistent_memory') is True else 'not declared'}.",
            f"- Generation temperature: {_cell(policy.get('temperature', 'not recorded'))}; "
            f"tools: {_cell(policy.get('tools', 'not recorded'))}.",
            f"- Serving policy by model: {_cell(json.dumps(policy['serving'], sort_keys=True)) if 'serving' in policy else 'not recorded; provider-controlled comparison not established'}.",
            f"- Resolved providers: {_cell(', '.join(summary.get('resolved_providers') or []) or 'not recorded')}.",
            f"- Source conversations: planned {_cell(summary.get('expected_transcripts', 'not recorded'))}; "
            f"generated {_cell(summary.get('transcript_count', 'not recorded'))}; evaluated in this scan {len(source.transcripts)}.",
            f"- Source generation elapsed seconds: {_cell(summary.get('elapsed_seconds', 'not recorded'))}.",
        ])
        lines.append("")
    lines.extend([
        f"Plan: {_link(PLAN_FILE, PLAN_FILE)} · SHA-256 `{plan_hash}`.", "",
        f"Answers: {_link(ANSWERS_FILE, ANSWERS_FILE)} · SHA-256 `{answers_hash}`.", "",
        f"Judgments: {_link(LEDGER_FILE, LEDGER_FILE)} · SHA-256 `{ledger_hash}`.", "",
        f"Corpus SHA-256: `{plan.scenario_corpus_sha256}`.", "",
        "</details>", "",
        "## Commentary", "",
        "Add the author, date, observation, and relevant check or transcript turns below. "
        "These notes do not change verdicts. Regeneration preserves this section for the same evidence.", "",
        COMMENTARY_MARKER,
    ])
    content = "\n".join(lines) + commentary
    temporary = output.with_suffix(".tmp")
    try:
        temporary.write_text(content)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return output
