from __future__ import annotations

from invisiblebench.export.safety_report_card import generate_safety_report_card


def test_raw_gate_report_quality_has_no_composite_or_rank() -> None:
    results = [
        {
            "model": "model-b",
            "scenario_id": "s1",
            "scenario": "Scenario 1",
            "gates": {
                "safety": {"passed": True, "reasons": []},
                "compliance": {"passed": True, "reasons": []},
            },
            "dimensions": {"regard": 0.9, "coordination": 0.4},
        },
        {
            "model": "model-a",
            "scenario_id": "s1",
            "scenario": "Scenario 1",
            "gates": {
                "safety": {"passed": True, "reasons": []},
                "compliance": {"passed": True, "reasons": []},
            },
            "dimensions": {"regard": 0.5, "coordination": 0.8},
        },
    ]

    quality = generate_safety_report_card(results)["quality"]

    assert [row["model"] for row in quality] == ["model-a", "model-b"]
    for row in quality:
        assert "regard" in row
        assert "coordination" in row
        assert "quality_score" not in row
        assert "overall_score" not in row
        assert "rank" not in row
