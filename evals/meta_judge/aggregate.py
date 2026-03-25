"""Aggregate meta-judge JSON results into labels.csv and summary stats."""

import csv
import json
import re
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"
OUTPUT_CSV = Path(__file__).parent / "labels.csv"
SUMMARY_FILE = Path(__file__).parent / "summary.md"

DIMENSIONS = [
    "safety_gate",
    "compliance_gate",
    "regard_recognition",
    "regard_agency",
    "regard_grounding",
    "regard_scaffolding",
    "coordination_resources",
    "coordination_navigation",
    "coordination_barriers",
    "coordination_engagement",
    "overall_agree",
]


def extract_json(text: str) -> dict | None:
    """Try to parse JSON from text, handling markdown fences."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
    return None


def main():
    results = []
    errors = []

    for f in sorted(RESULTS_DIR.glob("*.json")):
        raw = f.read_text()
        data = extract_json(raw)
        if data is None:
            errors.append(f.name)
            continue
        # Normalize scenario_id from filename if missing
        if "scenario_id" not in data:
            data["scenario_id"] = f.stem.split("_", 1)[1] if "_" in f.stem else f.stem
        results.append(data)

    if not results:
        print("No valid results found.")
        return

    # Write CSV
    fieldnames = ["scenario_id"] + DIMENSIONS + [d + "_rationale" for d in DIMENSIONS] + ["notes"]
    with open(OUTPUT_CSV, "w", newline="") as csvf:
        writer = csv.DictWriter(csvf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print(f"Wrote {len(results)} labels to {OUTPUT_CSV}")
    if errors:
        print(f"  {len(errors)} files had invalid JSON: {errors}")

    # Compute summary stats
    lines = [
        "# Meta-Judge Summary (GPT-5.4 via Codex)\n",
        f"Traces evaluated: {len(results)}\n",
        f"Parse errors: {len(errors)}\n",
        "",
    ]

    # Agreement rates per dimension
    lines.append("## Scorer Agreement\n")
    lines.append("| Dimension | Agree/Pass | Disagree/Fail | Agreement % |")
    lines.append("|-----------|-----------|---------------|-------------|")

    for dim in DIMENSIONS:
        values = [r.get(dim, "").lower() for r in results if r.get(dim)]
        agree = sum(1 for v in values if v in ("agree", "pass"))
        disagree = sum(1 for v in values if v in ("disagree", "fail"))
        total = agree + disagree
        pct = f"{agree / total * 100:.0f}%" if total > 0 else "N/A"
        lines.append(f"| {dim} | {agree} | {disagree} | {pct} |")

    # Disagreements detail
    lines.append("\n## Disagreements\n")
    for r in results:
        disagreements = []
        for dim in DIMENSIONS:
            v = r.get(dim, "").lower()
            if v in ("disagree", "fail"):
                rationale = r.get(f"{dim}_rationale", "")
                disagreements.append(f"  - **{dim}**: {rationale}")
        if disagreements:
            lines.append(f"### {r.get('scenario_id', '?')}\n")
            lines.append("\n".join(disagreements))
            if r.get("notes"):
                lines.append(f"  - **notes**: {r['notes']}")
            lines.append("")

    with open(SUMMARY_FILE, "w") as f:
        f.write("\n".join(lines))
    print(f"Wrote summary to {SUMMARY_FILE}")


if __name__ == "__main__":
    main()
