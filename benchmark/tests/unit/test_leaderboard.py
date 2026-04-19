"""Contract tests for public leaderboard artifact and generator strictness."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LEADERBOARD_PATH = REPO_ROOT / "data" / "leaderboard" / "leaderboard.json"


# ── Published artifact shape ─────────────────────────────────────────

class TestPublishedLeaderboardArtifact:
    """Assert the public leaderboard artifact has the expected published shape."""

    @pytest.fixture()
    def leaderboard(self) -> dict:
        return json.loads(LEADERBOARD_PATH.read_text())

    def test_artifact_exists(self):
        assert LEADERBOARD_PATH.exists()

    def test_metadata_has_core_fields(self, leaderboard):
        meta = leaderboard["metadata"]
        assert meta["benchmark_version"] == "2.1.0"
        assert meta["total_models"] >= 1
        assert meta["total_scenarios"] == 50

    def test_metadata_exposes_claim_surface_and_validation(self, leaderboard):
        meta = leaderboard["metadata"]
        methodology = meta["methodology"]

        assert methodology["claim_surface"]["primary"] == [
            "safety_gate_pass_rate",
            "compliance_gate_pass_rate",
            "public_hard_fail_rate",
        ]
        assert methodology["validation"]["public_hard_fail_layer"]["status"] == "validated"
        assert methodology["validation"]["public_hard_fail_layer"]["sample_size"] == 60
        assert methodology["validation"]["quality_layer"]["status"] == "in-progress"
        assert methodology["validation"]["quality_layer"]["components"]["regard"]["status"] == (
            "in-progress"
        )
        assert methodology["validation"]["quality_layer"]["components"]["regard"]["sample_size"] == 60
        assert meta["delivery"]["format"] == "static_json"

    def test_metadata_has_benchmark_version(self, leaderboard):
        assert leaderboard["metadata"]["benchmark_version"] == "2.1.0"

    def test_overall_leaderboard_populated(self, leaderboard):
        rows = leaderboard["overall_leaderboard"]
        assert len(rows) >= 1
        assert rows[0]["rank"] == 1
        assert all(rows[i]["overall_score"] >= rows[i + 1]["overall_score"] for i in range(len(rows) - 1))

    def test_required_sections_present(self, leaderboard):
        required = {
            "metadata",
            "overall_leaderboard",
            "dimension_leaderboards",
            "cost_efficiency",
            "safety_report_card",
            "quality_leaderboard",
        }
        assert required <= set(leaderboard.keys())


# ── Generator strictness ─────────────────────────────────────────────

class TestGeneratorStrictness:
    """Assert the leaderboard generator rejects legacy inputs."""

    def _write_result(self, tmp: Path, data: dict, name: str = "model.json") -> None:
        (tmp / name).write_text(json.dumps(data))

    def _valid_v21_result(self, **overrides) -> dict:
        base = {
            "model": "test-model",
            "model_id": "test/model-v1",
            "benchmark_version": "2.1.0",
            "overall_score": 0.8,
            "timestamp": "2026-03-25T00:00:00Z",
            "scenarios": [
                {
                    "scenario_id": "test_001",
                    "scenario": "Test",
                    "overall_score": 0.8,
                    "status": "pass",
                    "gates": {
                        "safety": {"passed": True, "reasons": []},
                        "compliance": {"passed": True, "reasons": []},
                    },
                }
            ],
        }
        base.update(overrides)
        return base

    def test_rejects_legacy_benchmark_version(self):
        from scripts.generate_leaderboard import verify_v21_compatible

        result = self._valid_v21_result(benchmark_version="v1.0.0")
        errors = verify_v21_compatible(result, "legacy.json")
        assert len(errors) >= 1
        assert "v1.0.0" in errors[0]

    def test_accepts_v21_result(self):
        from scripts.generate_leaderboard import verify_v21_compatible

        result = self._valid_v21_result()
        errors = verify_v21_compatible(result, "good.json")
        assert errors == []

    def test_load_rejects_mixed_version_strict(self):
        from scripts.generate_leaderboard import load_canonical_results

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._write_result(tmp_path, self._valid_v21_result(benchmark_version="v1.0.0"))

            with pytest.raises(ValueError, match="strict mode"):
                load_canonical_results(tmp_path, False, set(), strict=True)

    def test_recomputes_passed_failed(self):
        from scripts.generate_leaderboard import compute_rankings

        results = [
            {
                "model": "test",
                "overall_score": 0.8,
                "total_cost": 1.0,
                "benchmark_version": "2.1.0",
                # Top-level claims wrong values
                "scenario_count": 999,
                "passed": 999,
                "failed": 999,
                "scenarios": [
                    {"scenario_id": "s1", "overall_score": 0.9, "status": "pass"},
                    {"scenario_id": "s2", "overall_score": 0.0, "status": "fail"},
                    {"scenario_id": "s3", "overall_score": 0.7, "status": "pass"},
                ],
            }
        ]

        rows = compute_rankings(results)
        assert rows[0]["scenario_count"] == 3  # recomputed, not 999
        assert rows[0]["passed"] == 2
        assert rows[0]["failed"] == 1


class TestWebBenchSync:
    def test_sync_status_detects_drift_and_syncs(self, tmp_path: Path):
        from scripts.sync_web_bench_leaderboard import compute_sync_status, sync_leaderboard

        source = tmp_path / "leaderboard.json"
        target = tmp_path / "public" / "bench" / "leaderboard.json"

        source.write_text(
            json.dumps(
                {
                    "metadata": {
                        "benchmark_version": "2.1.0",
                        "generated_at": "2026-04-19T00:00:00+00:00",
                    }
                }
            )
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "metadata": {
                        "benchmark_version": "2.1.0",
                        "generated_at": "2026-04-01T00:00:00+00:00",
                    }
                }
            )
        )

        status = compute_sync_status(source, target)
        assert status.in_sync is False
        assert status.source_generated_at == "2026-04-19T00:00:00+00:00"
        assert status.target_generated_at == "2026-04-01T00:00:00+00:00"

        synced = sync_leaderboard(source, target)
        assert synced.in_sync is True
        assert target.read_text() == source.read_text()

    def test_sync_status_handles_missing_target(self, tmp_path: Path):
        from scripts.sync_web_bench_leaderboard import compute_sync_status

        source = tmp_path / "leaderboard.json"
        target = tmp_path / "missing" / "leaderboard.json"
        source.write_text(json.dumps({"metadata": {"generated_at": "2026-04-19T00:00:00+00:00"}}))

        status = compute_sync_status(source, target)
        assert status.in_sync is False
        assert status.target_hash is None
        assert status.target_generated_at is None
