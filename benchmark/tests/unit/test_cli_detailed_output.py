from __future__ import annotations

from pathlib import Path

from invisiblebench.cli.runner import write_detailed_outputs


def test_write_detailed_outputs_creates_files(tmp_path: Path) -> None:
    results = {
        "overall_score": 0.75,
        "dimension_scores": {"memory": {"score": 0.9}},
        "metadata": {"scenario_id": "test"},
    }

    paths = write_detailed_outputs(results, tmp_path, model_id="test/model", scenario_id="scenario_1")

    detail_json = Path(paths["detail_json"])
    detail_html = Path(paths["detail_html"])

    assert detail_json.exists()
    assert detail_html.exists()
