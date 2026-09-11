#!/usr/bin/env python3
"""Report per-check verdict deltas between a contrast anchor and its variants.

Read-only. It reads one completed or partial scan bundle and the scenario
corpus, groups judgments by `contrast_group`, and prints where a variant's
verdict differs from its anchor for the same model and check.

This is an analysis view over the existing judgment ledger. It derives no score,
category, or composite, and it writes nothing to the corpus or the leaderboard.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invisiblebench.judge import load_scan  # noqa: E402
from invisiblebench.models.scan import Verdict  # noqa: E402
from invisiblebench.utils.benchmark_inventory import (  # noqa: E402
    collect_public_scenario_paths,
    get_private_confidential_dir,
)

ANCHOR = "anchor"


def contrast_metadata(project_root: Path | None = None) -> dict[str, dict[str, str]]:
    """Map scenario_id to its contrast group and variable, for grouped scenarios."""
    paths = list(collect_public_scenario_paths(project_root))
    private = get_private_confidential_dir(project_root)
    if private is not None and private.exists():
        paths.extend(sorted(private.rglob("*.json")))
    grouped: dict[str, dict[str, str]] = {}
    for path in paths:
        data = json.loads(path.read_text())
        group = data.get("contrast_group")
        if not group:
            continue
        scenario_id = str(data.get("id") or data.get("scenario_id") or path.stem)
        grouped[scenario_id] = {
            "contrast_group": str(group),
            "contrast_variable": str(data.get("contrast_variable") or ""),
        }
    return grouped


def group_deltas(
    verdicts: dict[tuple[str, str], dict[str, str]],
    metadata: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Compare each variant against its group anchor for the same model and check."""
    anchors = {
        (model_id, metadata[scenario_id]["contrast_group"]): scenario_id
        for model_id, scenario_id in verdicts
        if metadata[scenario_id]["contrast_variable"] == ANCHOR
    }
    groups: dict[str, Any] = {}
    for (model_id, scenario_id), checks in sorted(verdicts.items()):
        group = metadata[scenario_id]["contrast_group"]
        variable = metadata[scenario_id]["contrast_variable"]
        if variable == ANCHOR:
            continue
        anchor_id = anchors.get((model_id, group))
        if anchor_id is None:
            groups.setdefault(group, {"anchor": None, "comparisons": []})
            continue
        anchor_checks = verdicts[model_id, anchor_id]
        differences = [
            {
                "check_id": check_id,
                "anchor": anchor_checks[check_id],
                "variant": verdict,
            }
            for check_id, verdict in sorted(checks.items())
            if check_id in anchor_checks
            and anchor_checks[check_id] != verdict
            and not (
                anchor_checks[check_id] == Verdict.NOT_APPLICABLE.value
                and verdict == Verdict.NOT_APPLICABLE.value
            )
        ]
        compared = sorted(set(checks) & set(anchor_checks))
        entry = groups.setdefault(group, {"anchor": anchor_id, "comparisons": []})
        entry["anchor"] = anchor_id
        entry["comparisons"].append(
            {
                "model_id": model_id,
                "variant_scenario_id": scenario_id,
                "contrast_variable": variable,
                "compared_checks": len(compared),
                "differing_checks": len(differences),
                "differences": differences,
            }
        )
    return groups


def contrast_report(bundle: Path, project_root: Path | None = None) -> dict[str, Any]:
    """Build the deterministic anchor-versus-variant view for one scan bundle."""
    _, records = load_scan(bundle)
    metadata = contrast_metadata(project_root)
    verdicts: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for record in records:
        if record.error is not None or record.scenario_id not in metadata:
            continue
        verdicts[record.model_id, record.scenario_id][record.check_id] = record.verdict.value
    return {"bundle": str(bundle), "groups": group_deltas(verdicts, metadata)}


def render(report: dict[str, Any]) -> str:
    lines = [f"Contrast deltas for {report['bundle']}"]
    if not report["groups"]:
        lines.append("  no contrast-grouped scenarios in this scan")
    for group, entry in sorted(report["groups"].items()):
        lines.append(f"\n{group} (anchor: {entry['anchor'] or 'MISSING'})")
        for comparison in entry["comparisons"]:
            lines.append(
                f"  {comparison['model_id']} | {comparison['contrast_variable']}"
                f" | {comparison['differing_checks']}/{comparison['compared_checks']}"
                " checks differ"
            )
            for difference in comparison["differences"]:
                lines.append(
                    f"      {difference['check_id']}: "
                    f"{difference['anchor']} -> {difference['variant']}"
                )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="A scan directory with scan_plan.json")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON")
    args = parser.parse_args()
    try:
        report = contrast_report(args.bundle)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
