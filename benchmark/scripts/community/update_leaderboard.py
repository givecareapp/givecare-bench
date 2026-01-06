#!/usr/bin/env python3
"""
Generate leaderboard from community submissions.

Updates website/leaderboard.html with latest results.

Usage:
    python benchmark/scripts/community/update_leaderboard.py
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def load_submissions(community_dir: Path) -> List[Dict]:
    """Load all valid submissions."""
    submissions = []

    for submission_file in community_dir.glob("*.json"):
        if submission_file.name == "TEMPLATE.json":
            continue

        with open(submission_file) as f:
            data = json.load(f)
            submissions.append(data)

    return submissions

def generate_leaderboard_html(submissions: List[Dict], output_path: Path):
    """Generate HTML leaderboard."""
    # Sort by overall score (descending)
    ranked = sorted(submissions, key=lambda x: x["results"]["overall_score"], reverse=True)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>InvisibleBench Leaderboard</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        header {{
            text-align: center;
            margin-bottom: 40px;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            margin: 0 0 10px 0;
        }}
        header p {{
            color: #666;
            margin: 5px 0;
        }}
        table {{
            width: 100%;
            background: white;
            border-collapse: collapse;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th {{
            background: #4CAF50;
            color: white;
            padding: 12px 8px;
            text-align: left;
            font-weight: 600;
            font-size: 13px;
        }}
        td {{
            padding: 12px 8px;
            border-bottom: 1px solid #eee;
            font-size: 13px;
        }}
        tr:hover {{
            background: #f9f9f9;
        }}
        .rank {{
            font-weight: bold;
            color: #4CAF50;
        }}
        .score {{
            font-weight: 600;
        }}
        .fail {{
            color: #f44336;
            font-weight: 600;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <header>
        <h1>InvisibleBench Community Leaderboard</h1>
        <p>Evaluating AI Safety and Quality in Long-Term Care Relationships</p>
        <p>Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M UTC")}</p>
        <p>Total submissions: {len(ranked)}</p>
    </header>

    <main>
        <table>
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Model</th>
                    <th>Overall</th>
                    <th>Crisis</th>
                    <th>Regulatory</th>
                    <th>Trauma</th>
                    <th>Belonging</th>
                    <th>Relational</th>
                    <th>Actionable</th>
                    <th>Longitudinal</th>
                    <th>Memory</th>
                    <th>Hard Fails</th>
                    <th>Submitter</th>
                </tr>
            </thead>
            <tbody>
"""

    for rank, sub in enumerate(ranked, 1):
        model = sub["model_info"]["name"]
        results = sub["results"]
        dims = results["dimension_scores"]
        submitter = sub["submitter"]["name"]
        fails = results["hard_fails"]["total"]

        fail_class = "fail" if fails > 0 else ""

        html += f"""                <tr>
                    <td class="rank">#{rank}</td>
                    <td><strong>{model}</strong></td>
                    <td class="score">{results['overall_score']:.3f}</td>
                    <td>{dims['crisis_safety']:.2f}</td>
                    <td>{dims['regulatory_fitness']:.2f}</td>
                    <td>{dims['trauma_informed_flow']:.2f}</td>
                    <td>{dims['belonging_cultural_fitness']:.2f}</td>
                    <td>{dims['relational_quality']:.2f}</td>
                    <td>{dims['actionable_support']:.2f}</td>
                    <td>{dims['longitudinal_consistency']:.2f}</td>
                    <td>{dims['memory_hygiene']:.2f}</td>
                    <td class="{fail_class}">{fails}</td>
                    <td>{submitter}</td>
                </tr>
"""

    html += """            </tbody>
        </table>
    </main>

    <footer class="footer">
        <p>Submit your results: <a href="https://github.com/givecareapp/givecare-bench">github.com/givecareapp/givecare-bench</a></p>
        <p>Questions? Email: ali@givecareapp.com</p>
    </footer>
</body>
</html>
"""

    output_path.write_text(html)
    print(f"Leaderboard updated: {output_path}")

def main():
    base_dir = Path(__file__).parent.parent.parent  # Project root
    community_dir = base_dir / "community" / "submissions"
    output_path = base_dir / "website" / "leaderboard.html"

    submissions = load_submissions(community_dir)

    print(f"Found {len(submissions)} submissions")

    if not submissions:
        print("No submissions yet - creating empty leaderboard")
        output_path.write_text("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>InvisibleBench Leaderboard</title>
</head>
<body>
    <h1>InvisibleBench Leaderboard</h1>
    <p>No submissions yet. Be the first to submit results!</p>
    <p><a href="https://github.com/givecareapp/givecare-bench">Submit your results</a></p>
</body>
</html>
""")
        return

    generate_leaderboard_html(submissions, output_path)
    print("Leaderboard generation complete!")

if __name__ == "__main__":
    main()
