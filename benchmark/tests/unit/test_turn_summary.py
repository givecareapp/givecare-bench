from __future__ import annotations

from invisiblebench.evaluation import orchestrator as orchestrator_module
from invisiblebench.export.reports import ReportGenerator


def test_build_turn_summary_collects_entries() -> None:
    dimension_scores = {
        "compliance": {
            "violations": [{"rule": "soft_medical", "turn": 2}],
            "hard_fails": [{"rule": "diagnosis", "turn": 3}],
        },
        "belonging": {
            "hard_fails": [{"rule": "demographic_stereotyping", "turn": 1}],
        },
        "memory": {"score": 1.0},
    }

    summary = orchestrator_module._build_turn_summary(dimension_scores)

    assert [entry["turn"] for entry in summary["entries"]] == [1, 2, 3]
    assert summary["entries"][0]["dimension"] == "belonging"
    assert summary["entries"][1]["rule"] == "soft_medical"
    assert summary["entries"][2]["severity"] == "hard_fail"
    assert 2 in summary["by_turn"]


def test_report_includes_turn_flags_section() -> None:
    generator = ReportGenerator()
    results = {
        "overall_score": 0.6,
        "dimension_scores": {},
        "turn_summary": {
            "entries": [
                {"turn": 2, "dimension": "compliance", "rule": "diagnosis", "severity": "hard_fail"}
            ]
        },
        "metadata": {},
    }

    html = generator._build_html(results)

    assert "Turn Flags" in html
    assert "compliance" in html
