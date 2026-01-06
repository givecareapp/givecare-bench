"""
Results export and leaderboard generation.
"""
import json
from pathlib import Path
from typing import Any, Dict, List

from invisiblebench.models import BenchmarkRun, DimensionType, ScenarioResult


class ResultsExporter:
    """Export benchmark results to JSON and generate leaderboards."""

    def __init__(self, output_dir: str = "./results"):
        """Initialize exporter with output directory."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_benchmark_run(self, run: BenchmarkRun) -> str:
        """
        Export complete benchmark run to JSON.

        Returns:
            Path to exported JSON file
        """
        # Create run directory
        run_dir = self.output_dir / run.run_id
        run_dir.mkdir(exist_ok=True)

        # Export full results
        full_results = {
            "run_id": run.run_id,
            "timestamp": run.timestamp,
            "models_tested": run.models_tested,
            "scenarios": run.scenarios,
            "results": [r.to_dict() for r in run.results]
        }

        results_file = run_dir / "full_results.json"
        with open(results_file, 'w') as f:
            json.dump(full_results, f, indent=2)

        # Export leaderboard
        leaderboard = run.get_leaderboard()
        leaderboard_file = run_dir / "leaderboard.json"
        with open(leaderboard_file, 'w') as f:
            json.dump(leaderboard, f, indent=2)

        # Export heatmap data
        heatmap_data = self._generate_heatmap_data(run)
        heatmap_file = run_dir / "heatmap.json"
        with open(heatmap_file, 'w') as f:
            json.dump(heatmap_data, f, indent=2)

        # Export summary report
        summary = self._generate_summary_report(run, leaderboard, heatmap_data)
        summary_file = run_dir / "summary.md"
        with open(summary_file, 'w') as f:
            f.write(summary)

        print(f"Results exported to: {run_dir}")
        print(f"- Full results: {results_file}")
        print(f"- Leaderboard: {leaderboard_file}")
        print(f"- Heatmap: {heatmap_file}")
        print(f"- Summary: {summary_file}")

        return str(run_dir)

    def _generate_heatmap_data(self, run: BenchmarkRun) -> Dict[str, Any]:
        """
        Generate heatmap data (dimensions × models).

        Returns data suitable for visualization libraries.
        """
        # Aggregate dimension scores by model
        model_dimension_scores = {}

        for result in run.results:
            if result.model_name not in model_dimension_scores:
                model_dimension_scores[result.model_name] = {}

            for dimension, score in result.final_scores.items():
                if dimension not in model_dimension_scores[result.model_name]:
                    model_dimension_scores[result.model_name][dimension] = []

                model_dimension_scores[result.model_name][dimension].append(score)

        # Calculate average scores
        heatmap = {
            "models": [],
            "dimensions": [dim.value for dim in DimensionType],
            "scores": []
        }

        for model_name in sorted(model_dimension_scores.keys()):
            heatmap["models"].append(model_name)

            model_scores = []
            for dimension in DimensionType:
                scores = model_dimension_scores[model_name].get(dimension, [0])
                avg_score = sum(scores) / len(scores) if scores else 0
                model_scores.append(round(avg_score, 2))

            heatmap["scores"].append(model_scores)

        return heatmap

    def _generate_summary_report(
        self,
        run: BenchmarkRun,
        leaderboard: List[Dict[str, Any]],
        heatmap_data: Dict[str, Any]
    ) -> str:
        """Generate markdown summary report."""
        report = f"""# InvisibleBench Results
## Run ID: {run.run_id}
**Date**: {run.timestamp}

---

## Leaderboard

| Rank | Model | Score | Max | % | Autofails | Scenarios Passed |
|------|-------|-------|-----|---|-----------|------------------|
"""

        for entry in leaderboard:
            report += f"| {entry['rank']} | {entry['model']} | {entry['score']:.1f} | {entry['max_possible']:.1f} | {entry['percentage']}% | {entry['autofails']} | {entry['scenarios_passed']} |\n"

        report += "\n---\n\n## Dimension Scores by Model\n\n"

        # Create dimension table
        report += "| Model | " + " | ".join([dim.value.replace('_', ' ').title() for dim in DimensionType]) + " |\n"
        report += "|-------|" + "|".join(["-------"] * len(DimensionType)) + "|\n"

        for model_name, scores in zip(heatmap_data["models"], heatmap_data["scores"]):
            report += f"| {model_name} | " + " | ".join([f"{s:.1f}" for s in scores]) + " |\n"

        report += "\n---\n\n## Key Findings\n\n"

        # Identify top performers
        if leaderboard:
            top_model = leaderboard[0]
            report += f"**Top Performer**: {top_model['model']} ({top_model['score']:.1f}/{top_model['max_possible']:.1f})\n\n"

            # Identify models with autofails
            models_with_autofails = [e for e in leaderboard if e['autofails'] > 0]
            if models_with_autofails:
                report += f"**Models with Safety Failures**: {len(models_with_autofails)} models triggered autofails\n"
                for entry in models_with_autofails[:5]:
                    report += f"- {entry['model']}: {entry['autofails']} autofails\n"
                report += "\n"

            # Identify dimension leaders
            report += "**Dimension Leaders**:\n"
            for dim_idx, dimension in enumerate(DimensionType):
                dim_scores = [(heatmap_data["models"][i], heatmap_data["scores"][i][dim_idx])
                              for i in range(len(heatmap_data["models"]))]
                dim_scores.sort(key=lambda x: x[1], reverse=True)
                if dim_scores:
                    leader = dim_scores[0]
                    report += f"- {dimension.value.replace('_', ' ').title()}: {leader[0]} ({leader[1]:.1f})\n"

        report += "\n---\n\n*Generated by InvisibleBench v0.1.0*\n"

        return report

    def export_scenario_result(
        self,
        result: ScenarioResult,
        output_file: str
    ):
        """Export individual scenario result with full turn details."""
        data = {
            "scenario_id": result.scenario_id,
            "model_name": result.model_name,
            "tier": result.tier.value,
            "total_score": result.total_score,
            "max_possible_score": result.max_possible_score,
            "final_scores": {dim.value: score for dim, score in result.final_scores.items()},
            "autofail_count": result.autofail_count,
            "passed": result.passed,
            "execution_time_seconds": result.execution_time_seconds,
            "turns": []
        }

        # Add turn details
        for turn_eval in result.turn_evaluations:
            turn_data = {
                "turn_number": turn_eval.turn_number,
                "session_number": turn_eval.session_number,
                "model_response": turn_eval.model_response.response_text,
                "aggregated_scores": {dim.value: score for dim, score in turn_eval.aggregated_scores.items()},
                "autofail": turn_eval.autofail,
                "autofail_reason": turn_eval.autofail_reason,
                "judge_evaluations": []
            }

            # Add judge evaluations
            for judge_eval in turn_eval.judge_evaluations:
                judge_data = {
                    "judge_name": judge_eval.judge_name,
                    "judge_model": judge_eval.judge_model,
                    "dimension_scores": {dim.value: score for dim, score in judge_eval.dimension_scores.items()},
                    "reasoning": judge_eval.reasoning,
                    "autofail_triggered": judge_eval.autofail_triggered,
                    "autofail_reason": judge_eval.autofail_reason
                }
                turn_data["judge_evaluations"].append(judge_data)

            data["turns"].append(turn_data)

        # Write to file
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"Scenario result exported to: {output_file}")


class LeaderboardHTMLGenerator:
    """Generate HTML leaderboard visualization (future enhancement)."""

    @staticmethod
    def generate_html(
        leaderboard: List[Dict[str, Any]],
        heatmap_data: Dict[str, Any],
        output_file: str
    ):
        """Generate interactive HTML leaderboard."""
        html = """<!DOCTYPE html>
<html>
<head>
    <title>InvisibleBench Leaderboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
        tr:nth-child(even) { background-color: #f2f2f2; }
        .autofail { color: red; font-weight: bold; }
        .pass { color: green; }
    </style>
</head>
<body>
    <h1>InvisibleBench Leaderboard</h1>
    <table>
        <tr>
            <th>Rank</th>
            <th>Model</th>
            <th>Score</th>
            <th>Percentage</th>
            <th>Autofails</th>
            <th>Scenarios Passed</th>
        </tr>
"""

        for entry in leaderboard:
            autofail_class = "autofail" if entry['autofails'] > 0 else "pass"
            # Escape model name to prevent XSS
            model_name = html.escape(str(entry['model']))
            html += f"""        <tr>
            <td>{entry['rank']}</td>
            <td>{model_name}</td>
            <td>{entry['score']:.1f}/{entry['max_possible']:.1f}</td>
            <td>{entry['percentage']}%</td>
            <td class="{autofail_class}">{entry['autofails']}</td>
            <td>{entry['scenarios_passed']}</td>
        </tr>
"""

        html += """    </table>
    <p><em>Generated by InvisibleBench v0.1.0</em></p>
</body>
</html>
"""

        with open(output_file, 'w') as f:
            f.write(html)

        print(f"HTML leaderboard generated: {output_file}")
