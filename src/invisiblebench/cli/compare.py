"""Side-by-side comparison of two judge ledgers over the same conversations.

The old ledger is a v1 `judgments.jsonl` written by the generative judge (one
row per attempt with `verdict`, `rationale`, `evidence`, `error`). The new
bundle is a v2 scan read through `load_scan`. Rows pair on model, scenario, and
check. The disagreements are the cases worth a human label; the page is the
first view of that queue. Read-only; no model calls.
"""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path
from typing import Any

from invisiblebench.judge import load_scan
from invisiblebench.models.scan import Verdict

VERDICTS = [verdict.value for verdict in Verdict]


def read_old_ledger(path: Path) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Last valid v1 attempt per (model, scenario, check)."""
    rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("error") is not None:
            continue
        key = (row["model_id"], row["scenario_id"], row["check_id"])
        rows[key] = {
            "verdict": row["verdict"],
            "rationale": row.get("rationale", ""),
            "evidence": row.get("evidence", []),
        }
    return rows


def compare_ledgers(old_bundle: Path, new_bundle: Path) -> dict[str, Any]:
    """Pair every new judgment with its old counterpart and summarize agreement."""
    old = read_old_ledger(Path(old_bundle) / "judgments.jsonl")
    plan, _answers, judgments = load_scan(Path(new_bundle))
    checks = {check.id: check for check in plan.checks}
    rows = []
    for judgment in judgments:
        key = judgment.key
        before = old.get(key)
        rows.append(
            {
                "model_id": judgment.model_id,
                "scenario_id": judgment.scenario_id,
                "check_id": judgment.check_id,
                "layer": checks[judgment.check_id].layer,
                "dimension": checks[judgment.check_id].dimension,
                "summary": checks[judgment.check_id].summary,
                "old": before,
                "new": {
                    "verdict": judgment.verdict.value,
                    "rationale": judgment.rationale,
                    "evidence": [span.model_dump() for span in judgment.evidence],
                    "answers": judgment.answers,
                },
                "agree": before is not None and before["verdict"] == judgment.verdict.value,
                "covered": before is not None,
            }
        )
    covered = [row for row in rows if row["covered"]]
    confusion = Counter((row["old"]["verdict"], row["new"]["verdict"]) for row in covered)
    by_check: dict[str, dict[str, int]] = {}
    for row in covered:
        entry = by_check.setdefault(row["check_id"], {"covered": 0, "agree": 0})
        entry["covered"] += 1
        entry["agree"] += int(row["agree"])
    return {
        "old_bundle": str(old_bundle),
        "new_bundle": str(new_bundle),
        "old_judge": "generative (v1 ledger)",
        "new_judge": plan.judge.model,
        "thresholds": plan.judge.thresholds.model_dump(),
        "judgments": len(rows),
        "covered": len(covered),
        "agree": sum(row["agree"] for row in covered),
        "confusion": {f"{a}->{b}": count for (a, b), count in sorted(confusion.items())},
        "by_check": by_check,
        "rows": rows,
    }


def _e(value: object) -> str:
    return html.escape(str(value))


def _evidence(spans: list[dict[str, Any]]) -> str:
    if not spans:
        return '<p class="muted">No cited turn.</p>'
    return "".join(
        f'<blockquote><span class="who">{_e(span["role"])} turn {_e(span["turn"])}</span>'
        f"{_e(span['quote'])}</blockquote>"
        for span in spans
    )


def _answers(answers: dict[str, float]) -> str:
    if not answers:
        return ""
    items = "".join(
        f"<li><code>{_e(key)}</code> {value:.2f}</li>" for key, value in sorted(answers.items())
    )
    return f"<details><summary>{len(answers)} probabilities</summary><ul>{items}</ul></details>"


def render_html(report: dict[str, Any]) -> str:
    """One self-contained page: summary, confusion, per-check agreement, then every pair."""
    rows = report["rows"]
    confusion_rows = "".join(
        f"<tr><td>{_e(transition)}</td><td>{count}</td></tr>"
        for transition, count in report["confusion"].items()
    )
    check_rows = "".join(
        f"<tr><td>{_e(check)}</td><td>{entry['agree']}/{entry['covered']}</td></tr>"
        for check, entry in sorted(
            report["by_check"].items(), key=lambda item: item[1]["agree"] / item[1]["covered"]
        )
    )
    cards = []
    for index, row in enumerate(rows, 1):
        old = row["old"]
        new = row["new"]
        state = "uncovered" if not row["covered"] else ("agree" if row["agree"] else "disagree")
        old_cell = (
            f'<div class="verdict v-{_e(old["verdict"])}">{_e(old["verdict"])}</div>'
            f"<p>{_e(old['rationale'])}</p>{_evidence(old['evidence'])}"
            if old
            else '<p class="muted">No old judgment for this pair.</p>'
        )
        cards.append(
            f'<section class="pair {state}" data-check="{_e(row["check_id"])}" '
            f'data-scenario="{_e(row["scenario_id"])}" data-state="{state}">'
            f'<header><span class="n">{index}</span> <b>{_e(row["check_id"])}</b> '
            f'<span class="muted">{_e(row["layer"])} / {_e(row["dimension"])}</span>'
            f'<div class="scenario">{_e(row["model_id"])} × {_e(row["scenario_id"])}</div>'
            f'<div class="summary">{_e(row["summary"])}</div></header>'
            f'<div class="cols"><div class="col"><h4>Old judge</h4>{old_cell}</div>'
            f'<div class="col"><h4>New judge</h4>'
            f'<div class="verdict v-{_e(new["verdict"])}">{_e(new["verdict"])}</div>'
            f"<p>{_e(new['rationale'])}</p>{_evidence(new['evidence'])}{_answers(new['answers'])}"
            f"</div></div></section>"
        )
    agree = report["agree"]
    covered = report["covered"]
    rate = f"{agree / covered:.0%}" if covered else "n/a"
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Judge comparison</title>
<style>
:root{{--bg:#fafaf7;--fg:#1a1a1a;--muted:#6b6b6b;--line:#e2e0d8;--card:#fff;--pass:#2e7d32;--fail:#c62828;--unclear:#b26a00;--na:#607d8b;--hl:#fff4d6}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--bg:#151513;--fg:#ececea;--muted:#9a9a94;--line:#2c2c28;--card:#1d1d1a;--hl:#3a3115}}}}
:root[data-theme="dark"]{{--bg:#151513;--fg:#ececea;--muted:#9a9a94;--line:#2c2c28;--card:#1d1d1a;--hl:#3a3115}}
body{{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif}}
main{{max-width:1100px;margin:0 auto}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:17px;margin:24px 0 8px}} h4{{margin:0 0 6px;color:var(--muted);font-weight:600}}
.muted{{color:var(--muted)}} table{{border-collapse:collapse;margin:8px 0}} td{{padding:3px 10px 3px 0;border-bottom:1px solid var(--line)}}
.bar{{display:flex;gap:8px;flex-wrap:wrap;position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line);z-index:1}}
.bar button{{border:1px solid var(--line);background:var(--card);color:var(--fg);padding:6px 10px;border-radius:6px;cursor:pointer}}
.bar button.on{{background:var(--fg);color:var(--bg)}}
.pair{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;margin:12px 0}}
.pair.disagree{{border-left:4px solid var(--fail)}} .pair.agree{{border-left:4px solid var(--pass)}} .pair.uncovered{{opacity:.75}}
.pair header .n{{color:var(--muted);margin-right:6px}} .scenario{{font-size:13px;color:var(--muted)}} .summary{{font-size:14px;margin-top:4px}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px}} @media (max-width:720px){{.cols{{grid-template-columns:1fr}}}}
.col{{min-width:0}} .col p{{margin:6px 0;font-size:14px;overflow-wrap:anywhere}}
.verdict{{display:inline-block;font-weight:700;padding:2px 8px;border-radius:4px;color:#fff}}
.v-PASS{{background:var(--pass)}} .v-FAIL{{background:var(--fail)}} .v-UNCLEAR{{background:var(--unclear)}} .v-NOT_APPLICABLE{{background:var(--na)}}
blockquote{{margin:6px 0;padding:6px 10px;border-left:3px solid var(--line);background:var(--hl);font-size:13px;white-space:pre-wrap;overflow-wrap:anywhere}}
blockquote .who{{display:block;font-size:12px;color:var(--muted);margin-bottom:2px}}
details{{font-size:13px;margin-top:6px}} details ul{{margin:4px 0;padding-left:18px}} code{{font-size:12px}}
.hidden{{display:none}}
</style></head><body><main>
<h1>Judge comparison</h1>
<p class="muted">Old: {_e(report["old_judge"])} · New: {_e(report["new_judge"])} (band {report["thresholds"]["low"]}–{report["thresholds"]["high"]}) · {_e(Path(report["old_bundle"]).name)} → {_e(Path(report["new_bundle"]).name)}</p>
<p><b>{agree}/{covered}</b> shared judgments agree ({rate}); {report["judgments"] - covered} new judgments have no old counterpart. Disagreements are the adjudication queue.</p>
<h2>Transitions (old → new)</h2><table>{confusion_rows}</table>
<h2>Agreement by check, lowest first</h2><table>{check_rows}</table>
<h2>Pairs</h2>
<div class="bar">
<button data-filter="disagree" class="on">Disagreements</button>
<button data-filter="all">All</button>
<button data-filter="agree">Agreements</button>
<input id="q" placeholder="filter by check or scenario" style="flex:1;min-width:160px;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg)">
</div>
<div id="pairs">{''.join(cards)}</div>
</main>
<script>
(function(){{
  var filter='disagree', q='';
  var buttons=document.querySelectorAll('.bar button');
  var pairs=document.querySelectorAll('.pair');
  function apply(){{
    pairs.forEach(function(p){{
      var okState = filter==='all' || p.dataset.state===filter;
      var text=(p.dataset.check+' '+p.dataset.scenario).toLowerCase();
      var okText = !q || text.indexOf(q)>=0;
      p.classList.toggle('hidden', !(okState && okText));
    }});
  }}
  buttons.forEach(function(b){{ b.addEventListener('click', function(){{
    buttons.forEach(function(x){{x.classList.remove('on')}}); b.classList.add('on'); filter=b.dataset.filter; apply();
  }}); }});
  document.getElementById('q').addEventListener('input', function(e){{ q=e.target.value.toLowerCase(); apply(); }});
  apply();
}})();
</script></body></html>
"""


def compare_command(args: Any) -> int:
    json_output = bool(getattr(args, "json_output", False))
    try:
        report = compare_ledgers(Path(args.old), Path(args.new))
        html_path = getattr(args, "html", None)
        if html_path:
            Path(html_path).write_text(render_html(report))
    except (OSError, ValueError, KeyError) as exc:
        if json_output:
            print(json.dumps({"status": "error", "command": "compare", "error": str(exc)}))
        else:
            print(f"error: {exc}")
        return 1
    if json_output:
        payload = {key: value for key, value in report.items() if key != "rows"}
        payload["disagreements"] = [
            {
                "scenario_id": row["scenario_id"],
                "check_id": row["check_id"],
                "old": row["old"]["verdict"],
                "new": row["new"]["verdict"],
            }
            for row in report["rows"]
            if row["covered"] and not row["agree"]
        ]
        print(json.dumps({"status": "ok", "command": "compare", "data": payload}, indent=2))
        return 0
    print(f"Shared judgments: {report['covered']}; agree: {report['agree']}")
    for transition, count in report["confusion"].items():
        print(f"  {transition}: {count}")
    print("Disagreements:")
    for row in report["rows"]:
        if row["covered"] and not row["agree"]:
            print(
                f"  {row['scenario_id']} {row['check_id']}: "
                f"{row['old']['verdict']} -> {row['new']['verdict']}"
            )
    if html_path:
        print(f"Page: {html_path}")
    return 0
