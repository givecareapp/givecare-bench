"""MkDocs hook: render owner facts and public exemplar evidence at build time."""

from __future__ import annotations

import html
import json
from collections import Counter

from invisiblebench.api.typesafe import DEFAULT_JUDGE_MODEL, validate_answers
from invisiblebench.evaluation import requests, rules
from invisiblebench.evaluation.check_registry import load_checks
from invisiblebench.examples import ANSWER_MAP, _read_jsonl, load_examples, requests_for
from invisiblebench.models.scan import Thresholds
from invisiblebench.utils.benchmark_inventory import get_project_root, load_inventory
from invisiblebench.version import ENGINE_VERSION

EXAMPLE_ID = "autonomy.coercion/immediate-placement-pressure"


def render_identity() -> str:
    inventory = load_inventory()
    return (
        f"**Benchmark {inventory['benchmark_version']} · engine {ENGINE_VERSION}**  \n"
        f"{inventory['standard_total']} public scenarios · {inventory['check_count']} checks. "
        "Protocol identity describes the implementation; it is not a result release."
    )


def _literal(text: str) -> str:
    return f"<pre>{html.escape(text)}</pre>"


def render_example() -> str:
    root = get_project_root() / "checks"
    checks = load_checks(root)
    directory, example = next(
        (directory, example)
        for directory, examples in load_examples(root, checks).items()
        for example in examples
        if example["id"] == EXAMPLE_ID
    )
    check = checks[example["check_id"]]
    saved_rows = {
        (row["role"], row["turn"], row["input_sha256"]): row
        for row in _read_jsonl(directory / "examples.answers.jsonl")
        if row["id"] == EXAMPLE_ID
    }
    saved, request_sections = {}, []
    for identity, request in requests_for(check, example).items():
        row = saved_rows.get(identity)
        if row is None or row["model"] != DEFAULT_JUDGE_MODEL:
            raise ValueError("public worked example has stale retained answers")
        typed = ANSWER_MAP.validate_python(row["answers"])
        validate_answers(typed, request["questions"])
        role, turn, digest = identity
        requests.merge_answers(saved, role, turn, typed)
        request_sections.extend(
            [
                f"### {role.title()} turn {turn}",
                "",
                f"input_sha256: `{digest}`",
                "",
                "Selected evidence and exact questions:",
                "",
                _literal(json.dumps(request, ensure_ascii=False, indent=2)),
                "",
                "Retained native answers:",
                "",
                _literal(json.dumps(row["answers"], ensure_ascii=False, indent=2)),
                "",
            ]
        )
    judgment = rules.derive(
        check,
        example["transcript"],
        saved,
        Thresholds(),
        model_id="exemplar",
        scenario_id=EXAMPLE_ID,
        plan_sha256="0" * 64,
    )
    if judgment.verdict.value != example["expected"]:
        raise ValueError("public worked example differs from its authored expectation")
    lines = [
        f"**Development exemplar:** `{EXAMPLE_ID}`.",
        "",
        "The caregiver messages and authored assistant response are synthetic. "
        "The probabilities below are retained Jev answers. This is a measured evaluator "
        "example, not a target-model result or held-out accuracy test.",
        "",
        "## Requirement",
        "",
        html.escape(check.summary),
        "",
        "**Requirement basis**",
        "",
        html.escape(check.basis),
        "",
        "**Narrow meaning of PASS**",
        "",
        html.escape(check.pass_meaning),
        "",
        "## Conversation",
        "",
    ]
    for turn in example["transcript"]:
        lines.extend(
            [f"**{turn['role'].title()} · turn {turn['turn']}**", "", _literal(turn["content"]), ""]
        )
    lines.extend(
        [
            "## Retained observations",
            "",
            f"Judge: `{DEFAULT_JUDGE_MODEL}`.",
            "",
            *request_sections,
            "## Rule and verdict",
            "",
            f"Thresholds: no ≤ {Thresholds().low}; yes ≥ {Thresholds().high}.",
            "",
            _literal(check.model_dump_json(indent=2)),
            "",
            f"**Derived verdict: {judgment.verdict.value}.**",
            "",
            html.escape(judgment.rationale),
            "",
            "### Cited evidence",
            "",
        ]
    )
    for span in judgment.evidence:
        lines.extend([f"{span.role.title()} turn {span.turn}:", "", _literal(span.quote), ""])
    source = "https://github.com/givecareapp/givecare-bench/blob/main/checks/safety/autonomy/"
    lines.extend(
        [
            f"[Public transcript]({source}examples.jsonl) · "
            f"[Saved answers]({source}examples.answers.jsonl) · "
            f"[Check definition]({source}{check.id}.yaml)",
            "",
        ]
    )
    return "\n".join(lines)


def render_coverage() -> str:
    inventory = load_inventory()
    root = get_project_root() / "checks"
    checks = load_checks(root)
    examples = [e for rows in load_examples(root, checks).values() for e in rows]
    lines = [
        "| Category | Public scenarios |",
        "| --- | ---: |",
        *(f"| {category} | {count} |" for category, count in inventory["categories"].items()),
        "",
        "The following table counts authored development controls. A FAIL control exercises "
        "a prohibited behavior; PASS and NOT_APPLICABLE controls preserve allowed behavior "
        "or test applicability. Counts do not establish coverage adequacy or judge accuracy.",
        "",
        "| Check | FAIL controls | PASS controls | NOT_APPLICABLE controls |",
        "| --- | ---: | ---: | ---: |",
    ]
    for check_id in sorted(checks):
        counts = Counter(e["expected"] for e in examples if e["check_id"] == check_id)
        lines.append(
            f"| `{check_id}` | {counts['FAIL']} | {counts['PASS']} | {counts['NOT_APPLICABLE']} |"
        )
    mapped = sum(len(row["mapped"]) for row in inventory["objective_coverage"])
    unmapped = sum(row["unmapped_objectives"] for row in inventory["objective_coverage"])
    lines.extend(
        [
            "",
            f"Scenario objectives: {mapped} mapped positions; {unmapped} unmapped objectives. "
            "These authoring links cannot force a verdict.",
        ]
    )
    return "\n".join(lines)


def on_page_markdown(markdown: str, **kwargs) -> str:
    for marker, render in {
        "<!-- benchmark:identity -->": render_identity,
        "<!-- benchmark:example -->": render_example,
        "<!-- benchmark:coverage -->": render_coverage,
    }.items():
        if marker in markdown:
            markdown = markdown.replace(marker, render())
    return markdown
