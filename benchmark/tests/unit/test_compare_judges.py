"""The comparison pairs old and new verdicts and renders the disagreement queue."""

from __future__ import annotations

import json
from types import SimpleNamespace

from benchmark.tests.fixtures.current_scan import ScriptedJudge, write_source_run
from invisiblebench.cli.compare import compare_command, compare_ledgers, render_html
from invisiblebench.judge import load_scan, plan_scan, run_scan


def _scan(tmp_path):
    source = write_source_run(tmp_path, roster=[("case", "context")])
    bundle = tmp_path / "scan"
    plan_scan([source], bundle)
    run_scan(bundle, max_cost_usd=0.5, client=ScriptedJudge({"cue": 0.9, "routing": 0.0}))
    return bundle


def _old_ledger(tmp_path, judgments):
    old = tmp_path / "old"
    old.mkdir()
    rows = []
    for index, judgment in enumerate(judgments):
        verdict = "PASS" if index else "FAIL"  # disagree on the first pair only
        rows.append(
            {
                "model_id": judgment.model_id,
                "scenario_id": judgment.scenario_id,
                "check_id": judgment.check_id,
                "verdict": verdict,
                "rationale": f"old reasoning {index}",
                "evidence": [{"role": "assistant", "turn": 1, "quote": "I can help."}],
                "error": None,
            }
        )
    rows.append({**rows[0], "verdict": "UNCLEAR", "error": "invalid_judge_output"})
    (old / "judgments.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    return old


def test_pairs_by_key_and_counts_agreement(tmp_path):
    bundle = _scan(tmp_path)
    judgments = load_scan(bundle)[2]
    old = _old_ledger(tmp_path, judgments)
    report = compare_ledgers(old, bundle)
    assert report["covered"] == len(judgments)
    new_first = judgments[0].verdict.value
    first = report["rows"][0]
    assert first["old"]["verdict"] == "FAIL" and first["new"]["verdict"] == new_first
    assert first["agree"] == (new_first == "FAIL")
    assert sum(row["agree"] for row in report["rows"]) == report["agree"]
    assert f"FAIL->{new_first}" in report["confusion"]
    # the invalid attempt did not overwrite the valid old row
    assert first["old"]["rationale"] == "old reasoning 0"


def test_html_holds_every_pair_and_the_filter(tmp_path):
    bundle = _scan(tmp_path)
    old = _old_ledger(tmp_path, load_scan(bundle)[2])
    page = render_html(compare_ledgers(old, bundle))
    assert page.count('<section class="pair') == len(load_scan(bundle)[2])
    assert "old reasoning 0" in page and "data-filter=\"disagree\"" in page
    assert "<script" in page and "prefers-color-scheme" in page


def test_command_writes_page_and_json(tmp_path, capsys):
    bundle = _scan(tmp_path)
    old = _old_ledger(tmp_path, load_scan(bundle)[2])
    out = tmp_path / "compare.html"
    args = SimpleNamespace(old=str(old), new=str(bundle), html=str(out), json_output=True)
    assert compare_command(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok" and "rows" not in payload["data"]
    assert out.exists()
    missing = SimpleNamespace(old=str(tmp_path / "nope"), new=str(bundle), html=None, json_output=True)
    assert compare_command(missing) == 1
