"""Render a run's Jury Card from its saved judgments, without model calls."""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from invisiblebench.judge import LEDGER_FILE, PLAN_FILE, load_scan, sha256
from invisiblebench.models.scan import Verdict
from invisiblebench.scoring import build_scorecard
from invisiblebench.utils.manifest import run_timestamp

CARD_FILE = "jury-card.md"
COMMENTARY_MARKER = "<!-- jury-card:commentary -->"


def _cell(value: object) -> str:
    return html.escape(str(value)).replace("|", "&#124;").replace("\n", "<br>")


def _link(label: str, path: str) -> str:
    return f"[{_cell(label)}]({quote(path, safe='/#')})"


def write_jury_card(bundle: Path) -> Path:
    """Write one Markdown report. Retain its commentary only for the same evidence."""
    bundle = Path(bundle)
    plan, attempts = load_scan(bundle, complete=True)
    scorecard = build_scorecard(bundle)
    records = [record for record in attempts if record.error is None]
    plan_hash = sha256((bundle / PLAN_FILE).read_bytes())
    ledger_hash = sha256((bundle / LEDGER_FILE).read_bytes())
    binding = f"<!-- jury-card:v1 plan={plan_hash} judgments={ledger_hash} -->"
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
    for record in attempts:
        first_attempts.setdefault(record.key, record)
    first_valid = sum(record.error is None for record in first_attempts.values())
    errors = Counter(record.error for record in attempts if record.error)
    judges = sorted({
        f"{record.judge.model or 'not recorded'} / {record.judge.provider or 'not recorded'}"
        for record in records
    })
    generation_costs = [summary.get("actual_cost_usd") for _, _, summary in sources]
    generation_cost = (
        sum(generation_costs) if all(value is not None for value in generation_costs) else None
    )
    judge_cost = sum(record.cost_usd for record in attempts)
    timestamp = run_timestamp(bundle, [manifest for _, manifest, _ in sources])
    date_label = f"{timestamp.day} {timestamp:%b %Y, %H:%M:%S} UTC" if timestamp else bundle.name
    models = scorecard["models"]
    model_label = models[0]["model"] if len(models) == 1 else f"{len(models)} models"
    lines = [
        f"# {_cell(model_label)} — {_cell(date_label)}", "", binding, "",
        "**Jury Card · MODEL-JUDGED. Care remains directional.** This card describes the recorded run. "
        "It does not establish clinical outcomes, general model quality, or judge accuracy.", "",
        "Read [commentary](#commentary) for attributed observations and disputed interpretations.", "",
        "| Model run | Jury assessment |", "| --- | --- |",
        f"| {len(plan.transcripts)} conversations | {len(plan.checks)} frozen checks per conversation |",
        f"| Benchmark {_cell(plan.benchmark_version)} | Engine {_cell(plan.engine_version)} |",
        f"| Source settings retained below | Judge: {_cell(plan.judge.model)} |",
        f"| Source transcripts retained below | Judge temperature: {plan.judge.temperature:g}; "
        f"context: {_cell(plan.judge.context_policy)} |",
        f"| Source generation cost: {'not recorded' if generation_cost is None else f'${generation_cost:.8f}'} "
        f"| Judgment cost, including technical attempts: ${judge_cost:.8f} |",
        "",
        "Generation costs and elapsed times describe the complete source runs, including any "
        "conversations outside this scan's selection.", "",
        *([f"Total recorded cost: **${generation_cost + judge_cost:.8f}**.", ""] if generation_cost is not None else []),
        "## Judge execution", "",
        f"- Completed judgments: {len(records)}.",
        f"- Valid first attempts: {first_valid}/{len(first_attempts)}. This measures format and "
        "evidence acceptance, not accuracy.",
        f"- Technical attempts: {sum(errors.values())}. "
        + "; ".join(f"{_cell(key)}: {count}" for key, count in sorted(errors.items())),
        f"- Returned judge/provider: {_cell('; '.join(judges))}.",
        "- Source hashes, quote provenance, decision binding, and complete coverage of the plan "
        "were checked when this card was generated.", "",
    ]
    checks = {check.id: check for check in plan.checks}
    refs = {(ref.model_id, ref.scenario_id): ref for ref in plan.transcripts}
    row_numbers = {record.key: i for i, record in enumerate(attempts, 1) if record.error is None}
    for model in scorecard["models"]:
        lines.extend([
            f"## {_cell(model['model'])}", "", f"Model: `{_cell(model['model_id'])}`.", "",
            "| Layer | Dimension | Observed result | PASS | FAIL | UNCLEAR | NOT_APPLICABLE |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: |",
        ])
        for layer in ("safety", "care"):
            for dimension, observation in model[layer].items():
                if layer == "safety":
                    n = observation["applicable_scenarios"]
                    result = f"{observation['failed_scenarios']}/{n} conversations failed" if n else "No applicable conversations"
                else:
                    n = observation["applicable_checks"]
                    result = f"{observation['counts']['PASS']}/{n} checks passed" if n else "No applicable checks"
                counts = " | ".join(str(observation["counts"][verdict.value]) for verdict in Verdict)
                lines.append(f"| {layer.title()} | {_cell(dimension)} | {result} | {counts} |")
        lines.extend([
            "", "Safety uses conversations; Care uses checks. Verdict counts use checks. "
            "UNCLEAR is unresolved and remains in applicable denominators. "
            "Zero observed failures is not evidence that unresolved cases passed.", "",
            "### Recorded failure modes and unresolved judgments", "",
        ])
        flagged = [record for record in records if record.model_id == model["model_id"]
                   and record.verdict in {Verdict.FAIL, Verdict.UNCLEAR}]
        if not flagged:
            lines.extend(["No FAIL or UNCLEAR judgments in this run.", ""])
        for check_id in sorted({record.check_id for record in flagged}):
            check = checks[check_id]
            lines.extend([
                f"#### {_cell(check_id)}", "",
                f"{check.layer.title()} / {_cell(check.dimension)} · {check.severity}. "
                f"{_link('Frozen criterion', PLAN_FILE)}: `{_cell(check_id)}`.", "",
                "| Model evidence | Judge's assessment |", "| --- | --- |",
            ])
            for record in flagged:
                if record.check_id != check_id:
                    continue
                ref = refs[record.model_id, record.scenario_id]
                evidence = "<br>".join(
                    f"{span.role} turn {span.turn}: “{_cell(span.quote)}”" for span in record.evidence
                ) or "No quote supplied."
                left = _link(record.scenario_id, ref.path) + "<br>" + evidence
                right = f"**{record.verdict.value}** — {_cell(record.rationale)}<br>" + _link(
                    f"Ledger row {row_numbers[record.key]}", f"{LEDGER_FILE}#L{row_numbers[record.key]}",
                )
                lines.append(f"| {left} | {right} |")
            lines.append("")

    lines.extend(["## Source records", ""])
    for source, manifest, summary in sources:
        policy = manifest.get("transcript_policy") or {}
        lines.extend([
            f"- Source run: `{_cell(manifest['run_id'])}`; {_cell(manifest.get('run_date', 'date not recorded'))}.",
            f"- {_link('Manifest and generation settings', source.manifest.path)} · "
            f"{_link('Run summary', source.summary.path)}.",
            f"- Generation temperature: {_cell(policy.get('temperature', 'not recorded'))}; "
            f"tools: {_cell(policy.get('tools', 'not recorded'))}.",
            f"- Source generation elapsed seconds: {_cell(summary.get('elapsed_seconds', 'not recorded'))}.",
        ])
        for ref in source.transcripts:
            lines.append(f"  - {_link(ref.model_id + ' / ' + ref.scenario_id, ref.path)}")
        lines.append("")
    lines.extend([
        f"Plan: {_link(PLAN_FILE, PLAN_FILE)} · SHA-256 `{plan_hash}`.", "",
        f"Judgments: {_link(LEDGER_FILE, LEDGER_FILE)} · SHA-256 `{ledger_hash}`.", "",
        f"Corpus SHA-256: `{plan.scenario_corpus_sha256}`.", "",
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
