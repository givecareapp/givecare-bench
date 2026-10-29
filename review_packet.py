"""Prepare a blind, source-bound human review packet from an Inspect generation log."""

import argparse
import hashlib
import json

from grader import family_files, target_samples


def build_packet(source_log: str) -> dict:
    samples, source = target_samples(source_log)
    items = []
    for sample in samples:
        prompt = json.loads(sample.input[-1].text)
        items.append({
            "item_id": str(sample.id),
            "family_id": str(sample.id).split("/", 1)[0],
            "criterion": prompt["criterion"],
            "response_turn": prompt["response_turn"],
            "conversation": prompt["conversation"],
        })
    return {
        "purpose": "Independent human labeling; development criteria, not validated claims",
        "family": source["family"],
        "source_log_sha256": source["source_log_sha256"],
        "case_sha256": source["case_sha256"],
        "rubric_sha256": hashlib.sha256(family_files(source["family"])[1].read_bytes()).hexdigest(),
        "benchmark_version": source["benchmark_version"],
        "planned_conversations": source["planned_samples"],
        "complete_conversations": source["complete_samples"],
        "items": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_log", help="Saved generation .eval log; no inference is run")
    args = parser.parse_args()
    print(json.dumps(build_packet(args.source_log), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
