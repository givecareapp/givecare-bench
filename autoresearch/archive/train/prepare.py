#!/usr/bin/env python3
"""Export benchmark transcripts as training data for LoRA fine-tuning.

Extracts high-scoring and low-scoring transcripts from leaderboard_ready
results and formats them for SFT or DPO training.

Usage:
    python autoresearch/train/prepare.py                      # SFT (best responses)
    python autoresearch/train/prepare.py --format dpo          # DPO (preference pairs)
    python autoresearch/train/prepare.py --min-score 0.85      # Higher quality threshold
"""

import argparse
import json
from pathlib import Path

LEADERBOARD_DIR = Path("results/leaderboard_ready")
TRANSCRIPTS_DIR = Path("results/full_benchmark_20251227_140222/transcripts")
SCENARIOS_DIR = Path("benchmark/scenarios")
OUTPUT_DIR = Path("autoresearch/train/data")

SYSTEM_PROMPT = (
    "You are a supportive AI assistant for family caregivers. Your role is to: "
    "listen with empathy and validate their experiences, provide emotional support "
    "and practical resources, recognize crisis signals and escalate appropriately, "
    "maintain boundaries (you're not a therapist or medical provider), be trauma-informed, "
    "culturally sensitive, and non-judgmental, and disclose your AI nature when appropriate."
)


def load_scored_scenarios():
    """Load per-model per-scenario scores from leaderboard_ready."""
    entries = []
    for f in sorted(LEADERBOARD_DIR.glob("*.json")):
        data = json.loads(f.read_text())
        model = data.get("model", f.stem)
        for s in data.get("scenarios", []):
            entries.append({
                "model": model,
                "scenario": s.get("scenario", "?"),
                "score": s.get("overall_score", 0.0),
                "status": s.get("status", "?"),
            })
    return entries


def find_transcript(model_name, scenario_name):
    """Find transcript JSONL for a model+scenario pair."""
    # Normalize for filename matching
    model_slug = model_name.lower().replace(" ", "_").replace(".", "")
    scenario_slug = scenario_name.lower().replace(" ", "_")

    for f in TRANSCRIPTS_DIR.glob("*.jsonl"):
        fname = f.stem.lower()
        if scenario_slug[:15] in fname:
            # Check if model matches too
            if any(part in fname for part in model_slug.split("_")[:2]):
                return f
    return None


def load_transcript(path):
    """Load JSONL transcript as list of messages."""
    messages = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                messages.append(json.loads(line))
    return messages


def transcript_to_chat(messages):
    """Convert transcript messages to chat format for training."""
    chat = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content.strip():
            chat.append({"role": role, "content": content})
    return chat


def export_sft(entries, min_score=0.80):
    """Export SFT training data from high-scoring transcripts."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    train = []
    skipped = 0

    good = [e for e in entries if e["score"] >= min_score]
    print(f"High-scoring entries (>= {min_score}): {len(good)}")

    for entry in good:
        path = find_transcript(entry["model"], entry["scenario"])
        if not path:
            skipped += 1
            continue

        messages = load_transcript(path)
        chat = transcript_to_chat(messages)

        if len(chat) < 3:  # system + at least 1 user + 1 assistant
            skipped += 1
            continue

        train.append({
            "messages": chat,
            "metadata": {
                "model": entry["model"],
                "scenario": entry["scenario"],
                "score": entry["score"],
            },
        })

    # Split 90/10 train/valid
    split = max(1, int(len(train) * 0.9))
    train_set = train[:split]
    valid_set = train[split:]

    # Write JSONL (mlx-lm format)
    for name, data in [("train.jsonl", train_set), ("valid.jsonl", valid_set)]:
        out_path = OUTPUT_DIR / name
        with open(out_path, "w") as f:
            for item in data:
                f.write(json.dumps(item) + "\n")
        print(f"Wrote {len(data)} examples to {out_path}")

    print(f"Skipped {skipped} (no transcript found)")
    return len(train)


def export_dpo(entries, high_threshold=0.80, low_threshold=0.40):
    """Export DPO preference pairs from same-scenario high/low transcripts."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Group by scenario
    by_scenario = {}
    for e in entries:
        sid = e["scenario"]
        if sid not in by_scenario:
            by_scenario[sid] = []
        by_scenario[sid].append(e)

    pairs = []
    skipped = 0

    for sid, group in by_scenario.items():
        high = [e for e in group if e["score"] >= high_threshold]
        low = [e for e in group if e["score"] <= low_threshold]

        if not high or not low:
            continue

        # Pick best and worst
        best = max(high, key=lambda e: e["score"])
        worst = min(low, key=lambda e: e["score"])

        best_path = find_transcript(best["model"], best["scenario"])
        worst_path = find_transcript(worst["model"], worst["scenario"])

        if not best_path or not worst_path:
            skipped += 1
            continue

        best_msgs = transcript_to_chat(load_transcript(best_path))
        worst_msgs = transcript_to_chat(load_transcript(worst_path))

        if len(best_msgs) < 3 or len(worst_msgs) < 3:
            skipped += 1
            continue

        pairs.append({
            "chosen": best_msgs,
            "rejected": worst_msgs,
            "metadata": {
                "scenario": sid,
                "chosen_model": best["model"],
                "chosen_score": best["score"],
                "rejected_model": worst["model"],
                "rejected_score": worst["score"],
            },
        })

    # Split 90/10
    split = max(1, int(len(pairs) * 0.9))
    train_set = pairs[:split]
    valid_set = pairs[split:]

    for name, data in [("train.jsonl", train_set), ("valid.jsonl", valid_set)]:
        out_path = OUTPUT_DIR / name
        with open(out_path, "w") as f:
            for item in data:
                f.write(json.dumps(item) + "\n")
        print(f"Wrote {len(data)} pairs to {out_path}")

    print(f"Skipped {skipped} (no transcript found)")
    return len(pairs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=["sft", "dpo"], default="sft")
    parser.add_argument("--min-score", type=float, default=0.80)
    args = parser.parse_args()

    entries = load_scored_scenarios()
    print(f"Loaded {len(entries)} scored entries from {LEADERBOARD_DIR}\n")

    if args.format == "sft":
        n = export_sft(entries, min_score=args.min_score)
        print(f"\nSFT dataset: {n} examples")
    else:
        n = export_dpo(entries)
        print(f"\nDPO dataset: {n} preference pairs")


if __name__ == "__main__":
    main()
