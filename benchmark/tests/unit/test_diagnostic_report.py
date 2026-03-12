from __future__ import annotations

import json
from pathlib import Path

from invisiblebench.export.diagnostic import generate_diagnostic_report


def test_generate_diagnostic_report_accepts_flat_all_results(tmp_path: Path) -> None:
    results_path = tmp_path / "all_results.json"
    results_path.write_text(
        json.dumps(
            [
                {
                    "model": "Model A",
                    "scenario": "Scenario 1",
                    "scenario_id": "s1",
                    "category": "safety",
                    "overall_score": 0.9,
                    "status": "pass",
                    "hard_fail": False,
                    "dimensions": {"regard": 0.9, "coordination": 0.9},
                },
                {
                    "model": "Model A",
                    "scenario": "Scenario 2",
                    "scenario_id": "s2",
                    "category": "context",
                    "overall_score": 0.0,
                    "status": "error",
                    "hard_fail": True,
                    "hard_fail_reasons": ["Transcript generation failed: timeout"],
                    "dimensions": {},
                },
            ]
        )
    )

    report = generate_diagnostic_report(str(results_path))

    assert "# Diagnostic Report" in report
    assert "Total Scenarios" in report
    assert "Scenario 2" in report
