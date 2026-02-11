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
            "        .turn-flag { background: #eef6ff; padding: 6px 10px; border-radius: 6px; font-size: 12px; display: inline-block; }",
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
                f"        <p><strong>LLM Enabled:</strong> {html.escape(str(metadata.get('llm_enabled', 'N/A')))}</p>",
                f"        <p><strong>Contract Version:</strong> {html.escape(str(metadata.get('scoring_contract_version', 'N/A')))}</p>",
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

        turn_summary = results.get("turn_summary", {})
        turn_entries = turn_summary.get("entries", []) if isinstance(turn_summary, dict) else []
        if turn_entries:
            html_parts.extend(
                [
                    "    <h2>Turn Flags</h2>",
                    "    <table>",
                    "        <thead>",
                    "            <tr><th>Turn</th><th>Dimension</th><th>Severity</th><th>Rule</th></tr>",
                    "        </thead>",
                    "        <tbody>",
                ]
            )
            for entry in turn_entries:
                html_parts.append(
                    "            <tr>"
                    f"<td>{html.escape(str(entry.get('turn', 'N/A')))}</td>"
                    f"<td>{html.escape(str(entry.get('dimension', 'unknown')))}</td>"
                    f"<td><span class='turn-flag'>{html.escape(str(entry.get('severity', '')))}</span></td>"
                    f"<td>{html.escape(str(entry.get('rule', '')))}</td>"
                    "</tr>"
                )
            html_parts.extend(["        </tbody>", "    </table>"])

        confidence = results.get("confidence") or {}
        overall_confidence = confidence.get("overall")
        overall_confidence_label = (
            "N/A" if overall_confidence is None else f"{overall_confidence:.3f}"
        )
        html_parts.extend(
            [
                "    <h3>Confidence</h3>",
                f"    <p><strong>Overall Confidence:</strong> {overall_confidence_label}</p>",
            ]
        )

        dimension_confidence = confidence.get("dimensions", {})
        if dimension_confidence:
            html_parts.extend(
                [
                    "    <table>",
                    "        <thead>",
                    "            <tr><th>Dimension</th><th>Confidence</th></tr>",
                    "        </thead>",
                    "        <tbody>",
                ]
            )
            for dimension, value in dimension_confidence.items():
                label = "N/A" if value is None else f"{value:.3f}"
                html_parts.append(
                    f"            <tr><td>{html.escape(str(dimension))}</td><td>{label}</td></tr>"
                )
            html_parts.extend(
                [
                    "        </tbody>",
                    "    </table>",
                ]
            )

        # Variance section (if multiple iterations)
        variance = results.get("variance")
        if variance and variance.get("overall"):
            overall_var = variance["overall"]
            html_parts.extend(
                [
                    "    <div style='margin: 20px 0; padding: 15px; background: #f0f0f0; border-radius: 5px;'>",
                    "        <h3 style='margin-top: 0;'>Variance Metrics (from multiple iterations)</h3>",
                    f"        <p><strong>Mean:</strong> {overall_var['mean']:.4f}</p>",
                    f"        <p><strong>Std Dev:</strong> {overall_var['std_dev']:.4f}</p>",
                    f"        <p><strong>Min:</strong> {overall_var['min']:.4f} | <strong>Max:</strong> {overall_var['max']:.4f}</p>",
                ]
            )
            if overall_var.get("cv") is not None:
                html_parts.append(
                    f"        <p><strong>Coefficient of Variation:</strong> {overall_var['cv']:.4f}</p>"
                )
            html_parts.append("    </div>")

        # Iterations detail
        iterations = results.get("iterations", [])
        if len(iterations) > 1:
            html_parts.extend(
                [
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
                ]
            )
            for iter_data in iterations:
                iter_num = iter_data.get("iteration", "?")
                iter_score = iter_data.get("overall_score", 0.0)
                iter_fail = "Yes" if iter_data.get("hard_fail", False) else "No"
                html_parts.append(
                    f"            <tr><td>{iter_num}</td><td>{iter_score:.4f}</td><td>{iter_fail}</td></tr>"
                )
            html_parts.extend(
                [
                    "        </tbody>",
                    "    </table>",
                ]
            )

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
                    rule = html.escape(str(violation.get("rule", "Unknown")))
                    turn = html.escape(str(violation.get("turn", "N/A")))
                    html_parts.append(f"        <div class='violation'>{rule} at turn {turn}</div>")

            html_parts.append("    </div>")

        # Close HTML
        html_parts.extend(["</body>", "</html>"])

        return "\n".join(html_parts)

    def generate_batch_report(self, results: list, output_path: str, metadata: dict = None) -> None:
        """
        Generate batch HTML report summarizing all scenario results.

        Args:
            results: List of scenario result dictionaries
            output_path: Path to write HTML file
            metadata: Optional run metadata (model, mode, etc.)
        """
        html_content = self._build_batch_html(results, metadata or {})
        with open(output_path, "w") as f:
            f.write(html_content)

    def _build_batch_html(self, results: list, metadata: dict) -> str:
        """Build batch summary HTML."""

        def is_failure(result: dict) -> bool:
            status = result.get("status")
            return (
                status in {"fail", "error"}
                or result.get("hard_fail")
                or result.get("overall_score", 1) < 0.5
            )

        # Calculate stats
        total = len(results)
        failures = [r for r in results if is_failure(r)]
        passed = total - len(failures)
        failed = len(failures)
        avg_score = sum(r.get("overall_score", 0) for r in results) / total if total else 0
        total_cost = sum(r.get("cost", 0) for r in results)

        # Group by category
        by_cat = {}
        for r in results:
            cat = r.get("category", r.get("tier", "unknown"))
            if cat not in by_cat:
                by_cat[cat] = []
            by_cat[cat].append(r)

        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "    <title>InvisibleBench Batch Report</title>",
            "    <style>",
            "        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }",
            "        .container { max-width: 900px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
            "        h1 { color: #333; margin-bottom: 10px; }",
            "        .subtitle { color: #666; margin-bottom: 30px; }",
            "        .stats { display: flex; gap: 30px; margin: 30px 0; }",
            "        .stat { text-align: center; }",
            "        .stat-value { font-size: 36px; font-weight: bold; }",
            "        .stat-label { color: #666; font-size: 14px; }",
            "        .pass { color: #28a745; }",
            "        .fail { color: #dc3545; }",
            "        .category-section { margin: 30px 0; }",
            "        .category-header { font-size: 18px; font-weight: bold; color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px; }",
            "        .scenario-row { display: flex; align-items: center; padding: 12px 0; border-bottom: 1px solid #f0f0f0; }",
            "        .scenario-name { flex: 1; }",
            "        .scenario-score { width: 80px; text-align: right; font-weight: bold; }",
            "        .scenario-status { width: 30px; text-align: center; }",
            "        .failure-section { background: #fff8f8; border: 1px solid #ffdddd; border-radius: 8px; padding: 20px; margin: 30px 0; }",
            "        .failure-item { margin: 20px 0; padding: 15px; background: white; border-left: 4px solid #dc3545; }",
            "        .failure-title { font-weight: bold; margin-bottom: 10px; }",
            "        .failure-reason { color: #dc3545; margin: 5px 0 5px 15px; }",
            "        .failure-detail { color: #666; font-size: 14px; margin: 3px 0 3px 15px; }",
            "        .dim-low { color: #856404; background: #fff3cd; padding: 2px 6px; border-radius: 3px; font-size: 12px; margin-right: 5px; }",
            "    </style>",
            "</head>",
            "<body>",
            "    <div class='container'>",
            "        <h1>InvisibleBench Report</h1>",
            f"        <div class='subtitle'>{html.escape(metadata.get('model', 'Unknown Model'))} &bull; {html.escape(metadata.get('mode', 'benchmark').upper())}</div>",
            "",
            "        <div class='stats'>",
            f"            <div class='stat'><div class='stat-value'>{avg_score*100:.0f}%</div><div class='stat-label'>Overall Score</div></div>",
            f"            <div class='stat'><div class='stat-value pass'>{passed}</div><div class='stat-label'>Passed</div></div>",
            f"            <div class='stat'><div class='stat-value fail'>{failed}</div><div class='stat-label'>Failed</div></div>",
            f"            <div class='stat'><div class='stat-value'>${total_cost:.3f}</div><div class='stat-label'>Cost</div></div>",
            "        </div>",
        ]

        # Results by category
        for cat in sorted(by_cat.keys()):
            cat_results = by_cat[cat]
            cat_avg = (
                sum(r.get("overall_score", 0) for r in cat_results) / len(cat_results)
                if cat_results
                else 0
            )
            html_parts.extend(
                [
                    "        <div class='category-section'>",
                    f"            <div class='category-header'>{html.escape(str(cat).capitalize())} &mdash; {cat_avg*100:.0f}%</div>",
                ]
            )
            for r in cat_results:
                score = r.get("overall_score", 0)
                is_fail = r.get("hard_fail") or score < 0.5
                status = "✗" if is_fail else "✓"
                status_class = "fail" if is_fail else "pass"
                html_parts.append(
                    f"            <div class='scenario-row'>"
                    f"<span class='scenario-status {status_class}'>{status}</span>"
                    f"<span class='scenario-name'>{html.escape(r.get('scenario', 'Unknown'))}</span>"
                    f"<span class='scenario-score'>{score*100:.0f}%</span>"
                    f"</div>"
                )
            html_parts.append("        </div>")

        # Failures section
        if failures:
            html_parts.extend(
                [
                    "        <div class='failure-section'>",
                    "            <h2 style='color: #dc3545; margin-top: 0;'>Failures &amp; Violations</h2>",
                ]
            )
            for f in failures:
                score_pct = int(f.get("overall_score", 0) * 100)
                html_parts.append(
                    f"            <div class='failure-item'>"
                    f"<div class='failure-title'>{html.escape(f.get('scenario', 'Unknown'))} ({html.escape(str(f.get('category', f.get('tier', '?'))))}) &mdash; {score_pct}%</div>"
                )

                # Hard fail reasons
                for reason in f.get("hard_fail_reasons", []):
                    html_parts.append(
                        f"                <div class='failure-reason'>→ {html.escape(str(reason))}</div>"
                    )

                # Failure categories
                categories = f.get("failure_categories", {})
                for cat, details in categories.get("details", {}).items():
                    cat_display = cat.replace("_", " ").title()
                    html_parts.append(
                        f"                <div class='failure-detail'>• {html.escape(cat_display)}</div>"
                    )
                    for detail in details[:2]:
                        html_parts.append(
                            f"                <div class='failure-detail' style='margin-left: 25px;'>{html.escape(str(detail))}</div>"
                        )

                # Low dimensions
                dims = f.get("dimensions", {})
                low_dims = [
                    (k, v) for k, v in dims.items() if isinstance(v, (int, float)) and v < 0.5
                ]
                if low_dims:
                    html_parts.append("                <div style='margin-top: 10px;'>")
                    for k, v in sorted(low_dims, key=lambda x: x[1]):
                        html_parts.append(
                            f"                    <span class='dim-low'>{html.escape(k)}: {int(v*100)}%</span>"
                        )
                    html_parts.append("                </div>")

                html_parts.append("            </div>")
            html_parts.append("        </div>")

        html_parts.extend(
            [
                "    </div>",
                "</body>",
                "</html>",
            ]
        )

        return "\n".join(html_parts)
