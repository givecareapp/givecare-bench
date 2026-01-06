"""
Report generators for InvisibleBench.

Generates HTML and JSON reports from scoring results.
"""
from __future__ import annotations

import html
import json
from typing import Any, Dict


class ReportGenerator:
    """Generates scoring reports."""

    def generate_json(self, results: Dict[str, Any], output_path: str) -> None:
        """
        Generate JSON report.

        Args:
            results: Scoring results dictionary
            output_path: Path to write JSON file
        """
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

    def generate_html(self, results: Dict[str, Any], output_path: str) -> None:
        """
        Generate HTML report.

        Args:
            results: Scoring results dictionary
            output_path: Path to write HTML file
        """
        html = self._build_html(results)
        with open(output_path, "w") as f:
            f.write(html)

    def _build_html(self, results: Dict[str, Any]) -> str:
        """Build HTML content from results."""
        overall_score = results.get("overall_score", 0.0)
        hard_fail = results.get("hard_fail", False)
        metadata = results.get("metadata", {})
        dimension_scores = results.get("dimension_scores", {})

        # Build HTML
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "    <title>InvisibleBench Report</title>",
            "    <style>",
            "        body { font-family: Arial, sans-serif; margin: 40px; }",
            "        h1 { color: #333; }",
            "        h2 { color: #666; border-bottom: 2px solid #ddd; }",
            "        .score { font-size: 48px; font-weight: bold; }",
            "        .pass { color: #28a745; }",
            "        .fail { color: #dc3545; }",
            "        .dimension { margin: 20px 0; padding: 15px; background: #f8f9fa; border-left: 4px solid #007bff; }",
            "        .dimension-name { font-weight: bold; font-size: 18px; }",
            "        .dimension-score { font-size: 24px; margin: 10px 0; }",
            "        .breakdown { font-size: 14px; color: #666; }",
            "        .violation { background: #fff3cd; padding: 10px; margin: 5px 0; border-left: 4px solid #ffc107; }",
            "        .hard-fail-banner { background: #f8d7da; border: 2px solid #f5c6cb; padding: 20px; margin: 20px 0; }",
            "        table { width: 100%; border-collapse: collapse; margin: 20px 0; }",
            "        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }",
            "        th { background-color: #f2f2f2; }",
            "    </style>",
            "</head>",
            "<body>",
            "    <h1>InvisibleBench Scoring Report</h1>",
        ]

        # Metadata section - escape user content to prevent XSS
        html_parts.extend(
            [
                "    <div class='metadata'>",
                f"        <p><strong>Scenario:</strong> {html.escape(str(metadata.get('scenario_id', 'N/A')))}</p>",
                f"        <p><strong>Jurisdiction:</strong> {html.escape(str(metadata.get('jurisdiction', 'N/A')))}</p>",
                f"        <p><strong>Timestamp:</strong> {html.escape(str(metadata.get('timestamp', 'N/A')))}</p>",
                f"        <p><strong>LLM Mode:</strong> {html.escape(str(metadata.get('llm_mode', 'N/A')))}</p>",
                "    </div>",
            ]
        )

        # Hard fail banner
        if hard_fail:
            html_parts.extend(
                [
                    "    <div class='hard-fail-banner'>",
                    "        <h2 style='color: #721c24; margin-top: 0;'>HARD FAIL</h2>",
                    "        <p>This evaluation failed due to critical violations:</p>",
                    "        <ul>",
                ]
            )
            for reason in results.get("hard_fail_reasons", []):
                html_parts.append(f"            <li>{html.escape(str(reason))}</li>")
            html_parts.extend(["        </ul>", "    </div>"])

        # Overall score
        score_class = "fail" if overall_score < 0.5 else "pass"
        html_parts.extend(
            [
                "    <h2>Overall Score</h2>",
                f"    <div class='score {score_class}'>{overall_score:.2f}</div>",
            ]
        )

        # Variance section (if multiple iterations)
        variance = results.get("variance")
        if variance and variance.get("overall"):
            overall_var = variance["overall"]
            html_parts.extend([
                "    <div style='margin: 20px 0; padding: 15px; background: #f0f0f0; border-radius: 5px;'>",
                "        <h3 style='margin-top: 0;'>Variance Metrics (from multiple iterations)</h3>",
                f"        <p><strong>Mean:</strong> {overall_var['mean']:.4f}</p>",
                f"        <p><strong>Std Dev:</strong> {overall_var['std_dev']:.4f}</p>",
                f"        <p><strong>Min:</strong> {overall_var['min']:.4f} | <strong>Max:</strong> {overall_var['max']:.4f}</p>",
            ])
            if overall_var.get("cv") is not None:
                html_parts.append(f"        <p><strong>Coefficient of Variation:</strong> {overall_var['cv']:.4f}</p>")
            html_parts.append("    </div>")

        # Iterations detail
        iterations = results.get("iterations", [])
        if len(iterations) > 1:
            html_parts.extend([
                "    <h3>Iteration Details</h3>",
                "    <table>",
                "        <thead>",
                "            <tr>",
                "                <th>Iteration</th>",
                "                <th>Overall Score</th>",
                "                <th>Hard Fail</th>",
                "            </tr>",
                "        </thead>",
                "        <tbody>",
            ])
            for iter_data in iterations:
                iter_num = iter_data.get("iteration", "?")
                iter_score = iter_data.get("overall_score", 0.0)
                iter_fail = "Yes" if iter_data.get("hard_fail", False) else "No"
                html_parts.append(
                    f"            <tr><td>{iter_num}</td><td>{iter_score:.4f}</td><td>{iter_fail}</td></tr>"
                )
            html_parts.extend([
                "        </tbody>",
                "    </table>",
            ])

        # Dimension scores
        html_parts.append("    <h2>Dimension Scores</h2>")

        # Get dimension variance if available
        dimension_variance = {}
        if variance and variance.get("dimensions"):
            dimension_variance = variance["dimensions"]

        for dimension, dim_result in dimension_scores.items():
            dim_score = dim_result.get("score", 0.0)
            score_class = "fail" if dim_score < 0.5 else "pass"

            html_parts.extend(
                [
                    "    <div class='dimension'>",
                    f"        <div class='dimension-name'>{html.escape(str(dimension).title())}</div>",
                    f"        <div class='dimension-score {score_class}'>{dim_score:.2f}</div>",
                ]
            )

            # Add dimension variance if available
            if dimension in dimension_variance:
                dim_var = dimension_variance[dimension]
                html_parts.append(
                    f"        <div style='font-size: 12px; color: #666; margin: 5px 0;'>"
                    f"σ={dim_var['std_dev']:.4f}, range=[{dim_var['min']:.2f}, {dim_var['max']:.2f}]</div>"
                )

            # Breakdown
            if "breakdown" in dim_result:
                html_parts.append("        <div class='breakdown'>")
                for key, value in dim_result["breakdown"].items():
                    if isinstance(value, (int, float)):
                        html_parts.append(f"            <div>{key}: {value:.2f}</div>")
                html_parts.append("        </div>")

            # Violations - escape content to prevent XSS
            if "violations" in dim_result and dim_result["violations"]:
                html_parts.append("        <h4>Violations:</h4>")
                for violation in dim_result["violations"]:
                    rule = html.escape(str(violation.get('rule', 'Unknown')))
                    turn = html.escape(str(violation.get('turn', 'N/A')))
                    html_parts.append(
                        f"        <div class='violation'>{rule} at turn {turn}</div>"
                    )

            html_parts.append("    </div>")

        # Close HTML
        html_parts.extend(["</body>", "</html>"])

        return "\n".join(html_parts)
