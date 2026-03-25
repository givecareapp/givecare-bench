#!/usr/bin/env bash
# Meta-judge: use Codex CLI (GPT-5.4) to evaluate each trace against the annotation rubric.
# Outputs one JSON file per trace in results/, then aggregates into labels.csv.

set -euo pipefail
cd "$(dirname "$0")"

TRACES_DIR="traces"
RESULTS_DIR="results"
RUBRIC="$(pwd)/../annotation_rubric.md"
PROMPT_FILE="$(pwd)/prompt.md"

mkdir -p "$RESULTS_DIR"

# Count total and already-done
total=$(ls "$TRACES_DIR"/*.md 2>/dev/null | wc -l)
done_count=$(ls "$RESULTS_DIR"/*.json 2>/dev/null | wc -l)
echo "=== Meta-Judge (GPT-5.4 via Codex) ==="
echo "Traces: $total | Already done: $done_count"
echo ""

for trace_file in "$TRACES_DIR"/*.md; do
  basename=$(basename "$trace_file" .md)
  result_file="$RESULTS_DIR/${basename}.json"

  # Skip if already evaluated
  if [ -f "$result_file" ]; then
    echo "SKIP $basename (already done)"
    continue
  fi

  echo -n "EVAL $basename ... "

  # Build the prompt: rubric context + trace + structured output request
  # Codex reads files referenced in the prompt
  codex exec --dangerously-bypass-approvals-and-sandbox \
    "$(cat "$PROMPT_FILE")

--- TRACE FILE ---
$(cat "$trace_file")
" > "$result_file" 2>/dev/null || {
    echo "FAILED"
    rm -f "$result_file"
    continue
  }

  # Validate JSON output
  if python3 -c "import json; json.load(open('$result_file'))" 2>/dev/null; then
    echo "OK"
  else
    echo "BAD JSON — retrying"
    rm -f "$result_file"

    codex exec --dangerously-bypass-approvals-and-sandbox \
      "$(cat "$PROMPT_FILE")

--- TRACE FILE ---
$(cat "$trace_file")

CRITICAL: Output ONLY valid JSON. No markdown, no explanation, no code fences." > "$result_file" 2>/dev/null || {
      echo "FAILED (retry)"
      rm -f "$result_file"
      continue
    }

    if python3 -c "import json; json.load(open('$result_file'))" 2>/dev/null; then
      echo "OK (retry)"
    else
      echo "SKIP (bad JSON after retry)"
      rm -f "$result_file"
    fi
  fi
done

# Aggregate results
echo ""
echo "=== Aggregating ==="
python3 aggregate.py
