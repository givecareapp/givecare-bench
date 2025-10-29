"""
Test suite for CLI integration.

Tests that the CLI properly wires all components together.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# Get paths relative to this test file
TEST_DIR = Path(__file__).parent
FIXTURES_DIR = TEST_DIR.parent / "fixtures"
PROJECT_ROOT = TEST_DIR.parent.parent
SCENARIOS_DIR = PROJECT_ROOT / "scenarios"
CONFIGS_DIR = PROJECT_ROOT / "configs"


class TestCLI:
    """Test command-line interface."""

    def test_cli_with_all_arguments(self):
        """Should run successfully with all required arguments."""
        from supportbench.yaml_cli import main

        import tempfile

        # Check if required files exist
        scenario_file = SCENARIOS_DIR / "care-burnout-arc-01.yaml"
        if not scenario_file.exists():
            pytest.skip(f"Scenario file not found: {scenario_file}")

        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = str(Path(tmpdir) / "report.html")
            json_path = str(Path(tmpdir) / "results.json")

            argv = [
                "--scenario",
                str(scenario_file),
                "--transcript",
                str(FIXTURES_DIR / "sample_transcript.jsonl"),
                "--rules",
                str(CONFIGS_DIR / "rules" / "ny.yaml"),
                "--out",
                html_path,
                "--json",
                json_path,
            ]

            exit_code = main(argv)

            # Should succeed
            assert exit_code == 0

            # Should create output files
            assert Path(html_path).exists()
            assert Path(json_path).exists()

    def test_cli_creates_valid_json_output(self):
        """Should create valid JSON output file."""
        from supportbench.yaml_cli import main

        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = str(Path(tmpdir) / "results.json")

            argv = [
                "--scenario",
                str(SCENARIOS_DIR / "care-burnout-arc-01.yaml"),
                "--transcript",
                str(FIXTURES_DIR / "sample_transcript.jsonl"),
                "--rules",
                str(CONFIGS_DIR / "rules" / "base.yaml"),
                "--json",
                json_path,
            ]

            exit_code = main(argv)
            assert exit_code == 0

            # Load and validate JSON
            with open(json_path) as f:
                results = json.load(f)

            assert "overall_score" in results
            assert "dimension_scores" in results
            assert "memory" in results["dimension_scores"]
            assert "trauma" in results["dimension_scores"]
            assert "belonging" in results["dimension_scores"]
            assert "compliance" in results["dimension_scores"]
            assert "safety" in results["dimension_scores"]

    def test_cli_without_optional_outputs(self):
        """Should run successfully without HTML/JSON output specified."""
        from supportbench.yaml_cli import main

        argv = [
            "--scenario",
            str(SCENARIOS_DIR / "care-burnout-arc-01.yaml"),
            "--transcript",
            str(FIXTURES_DIR / "sample_transcript.jsonl"),
            "--rules",
            str(CONFIGS_DIR / "rules" / "ny.yaml"),
        ]

        exit_code = main(argv)

        # Should succeed and print results to stdout
        assert exit_code == 0

    def test_cli_missing_required_args_fails(self):
        """Should fail when required arguments are missing."""
        from supportbench.yaml_cli import main

        # Missing --transcript
        argv = [
            "--scenario",
            str(SCENARIOS_DIR / "care-burnout-arc-01.yaml"),
            "--rules",
            str(CONFIGS_DIR / "rules" / "base.yaml"),
        ]

        with pytest.raises(SystemExit) as exc_info:
            main(argv)

        # Should exit with error code
        assert exc_info.value.code != 0

    def test_cli_nonexistent_scenario_fails(self):
        """Should fail gracefully with nonexistent scenario file."""
        from supportbench.yaml_cli import main

        argv = [
            "--scenario",
            "/nonexistent/scenario.yaml",
            "--transcript",
            str(FIXTURES_DIR / "sample_transcript.jsonl"),
            "--rules",
            str(CONFIGS_DIR / "rules" / "base.yaml"),
        ]

        exit_code = main(argv)

        # Should fail
        assert exit_code != 0

    def test_cli_nonexistent_transcript_fails(self):
        """Should fail gracefully with nonexistent transcript file."""
        from supportbench.yaml_cli import main

        argv = [
            "--scenario",
            str(SCENARIOS_DIR / "care-burnout-arc-01.yaml"),
            "--transcript",
            "/nonexistent/transcript.jsonl",
            "--rules",
            str(CONFIGS_DIR / "rules" / "base.yaml"),
        ]

        exit_code = main(argv)

        # Should fail
        assert exit_code != 0

    def test_cli_html_output_contains_scores(self):
        """Should generate HTML with dimension scores."""
        from supportbench.yaml_cli import main

        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = str(Path(tmpdir) / "report.html")

            argv = [
                "--scenario",
                str(SCENARIOS_DIR / "care-burnout-arc-01.yaml"),
                "--transcript",
                str(FIXTURES_DIR / "sample_transcript.jsonl"),
                "--rules",
                str(CONFIGS_DIR / "rules" / "ny.yaml"),
                "--out",
                html_path,
            ]

            exit_code = main(argv)
            assert exit_code == 0

            html_content = Path(html_path).read_text()

            # Should contain dimension names
            assert "Memory" in html_content
            assert "Trauma" in html_content
            assert "Belonging" in html_content
            assert "Compliance" in html_content
            assert "Safety" in html_content


class TestEndToEndSmoke:
    """End-to-end smoke tests with real fixtures."""

    def test_complete_pipeline_with_good_transcript(self):
        """Should score well with compliant transcript."""
        from supportbench.yaml_cli import main

        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = str(Path(tmpdir) / "results.json")

            argv = [
                "--scenario",
                str(SCENARIOS_DIR / "care-burnout-arc-01.yaml"),
                "--transcript",
                "" + str(FIXTURES_DIR / "sample_transcript.jsonl"),
                "--rules",
                str(CONFIGS_DIR / "rules" / "ny.yaml"),
                "--json",
                json_path,
            ]

            exit_code = main(argv)
            assert exit_code == 0

            with open(json_path) as f:
                results = json.load(f)

            # Sample transcript is well-designed, should score reasonably
            assert results["overall_score"] > 0.5

            # Should have detected crisis appropriately
            safety = results["dimension_scores"]["safety"]
            assert safety["crisis_detected"] is True

            # Should not have hard fails
            assert results["hard_fail"] is False

    def test_complete_pipeline_with_ny_rules(self):
        """Should apply NY-specific rules correctly."""
        from supportbench.yaml_cli import main

        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = str(Path(tmpdir) / "results.json")

            argv = [
                "--scenario",
                str(SCENARIOS_DIR / "care-burnout-arc-01.yaml"),
                "--transcript",
                "" + str(FIXTURES_DIR / "sample_transcript.jsonl"),
                "--rules",
                str(CONFIGS_DIR / "rules" / "ny.yaml"),
                "--json",
                json_path,
            ]

            exit_code = main(argv)
            assert exit_code == 0

            with open(json_path) as f:
                results = json.load(f)

            # NY requires crisis detection
            assert results["metadata"]["jurisdiction"] == "ny"

    def test_pipeline_produces_both_outputs(self):
        """Should produce both HTML and JSON when requested."""
        from supportbench.yaml_cli import main

        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = str(Path(tmpdir) / "report.html")
            json_path = str(Path(tmpdir) / "results.json")

            argv = [
                "--scenario",
                str(SCENARIOS_DIR / "care-burnout-arc-01.yaml"),
                "--transcript",
                "" + str(FIXTURES_DIR / "sample_transcript.jsonl"),
                "--rules",
                str(CONFIGS_DIR / "rules" / "base.yaml"),
                "--out",
                html_path,
                "--json",
                json_path,
            ]

            exit_code = main(argv)
            assert exit_code == 0

            # Both files should exist
            assert Path(html_path).exists()
            assert Path(json_path).exists()

            # HTML should have content
            assert Path(html_path).stat().st_size > 100

            # JSON should be valid
            with open(json_path) as f:
                results = json.load(f)
                assert "overall_score" in results
