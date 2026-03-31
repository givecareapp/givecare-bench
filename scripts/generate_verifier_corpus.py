#!/usr/bin/env python3
"""Generate a verifier corpus manifest for the current 15-model board."""

from __future__ import annotations

import argparse
import json

from invisiblebench.utils.benchmark_inventory import get_project_root
from invisiblebench.utils.verifier_corpus import (
    CURRENT_BOARD_LEADERBOARD_DIR,
    CURRENT_BOARD_TRANSCRIPT_DIRS,
    build_verifier_corpus_summary,
    write_verifier_corpus_manifest,
    write_verifier_corpus_summary,
)


def _render_summary_markdown(summary: dict) -> str:
    lines = [
        "# Verifier Corpus Summary",
        "",
        f"- traces: **{summary['traces']}**",
        f"- models: **{summary['models']}**",
        f"- transcript coverage: **{summary['transcripts_found']}/{summary['traces']}**",
        f"- resolved detail_json: **{summary['detail_json_found']}/{summary['traces']}**",
        f"- resolved detail_html: **{summary['detail_html_found']}/{summary['traces']}**",
        f"- error rows: **{summary['error_rows']}**",
        f"- hard fails: **{summary['hard_fails']}**",
        "",
        "## By model",
        "",
        "| Model | Traces | Transcripts | Error rows | Hard fails | detail_json | detail_html | Source runs |",
        "|-------|-------:|------------:|-----------:|-----------:|------------:|------------:|-------------|",
    ]
    for row in summary["models_by_name"]:
        lines.append(
            "| {model} | {traces} | {transcripts_found} | {error_rows} | {hard_fails} | {detail_json_found} | {detail_html_found} | {source_runs} |".format(
                model=row["model"],
                traces=row["traces"],
                transcripts_found=row["transcripts_found"],
                error_rows=row["error_rows"],
                hard_fails=row["hard_fails"],
                detail_json_found=row["detail_json_found"],
                detail_html_found=row["detail_html_found"],
                source_runs=", ".join(row["source_runs"]) or "—",
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="internal/evals/verifier/corpus_manifest.jsonl",
        help="Where to write the JSONL manifest.",
    )
    parser.add_argument(
        "--summary-json",
        default="internal/evals/verifier/corpus_summary.json",
        help="Where to write the machine-readable summary.",
    )
    parser.add_argument(
        "--summary-md",
        default="internal/evals/verifier/corpus_summary.md",
        help="Where to write the human-readable summary.",
    )
    args = parser.parse_args()

    project_root = get_project_root()
    manifest = write_verifier_corpus_manifest(
        project_root,
        project_root / args.output,
        leaderboard_dir=CURRENT_BOARD_LEADERBOARD_DIR,
        transcript_dirs=CURRENT_BOARD_TRANSCRIPT_DIRS,
    )
    summary = build_verifier_corpus_summary(manifest)
    write_verifier_corpus_summary(summary, project_root / args.summary_json)
    summary_md_path = project_root / args.summary_md
    summary_md_path.parent.mkdir(parents=True, exist_ok=True)
    summary_md_path.write_text(_render_summary_markdown(summary))

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
