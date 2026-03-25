#!/usr/bin/env bash
# Parallel meta-judge: run N concurrent Codex evaluations.
set -euo pipefail
cd "$(dirname "$0")"

TRACES_DIR="traces"
RESULTS_DIR="results"
PROMPT_FILE="$(pwd)/prompt.md"
MAX_PARALLEL=${1:-5}

mkdir -p "$RESULTS_DIR"

eval_trace() {
  local trace_file="$1"
  local basename
  basename=$(basename "$trace_file" .md)
  local result_file="$RESULTS_DIR/${basename}.json"

  # Skip if already done
  if [ -f "$result_file" ] && python3 -c "import json; json.load(open('$result_file'))" 2>/dev/null; then
    echo "SKIP $basename"
    return 0
  fi

  local prompt
  prompt="$(cat "$PROMPT_FILE")

--- TRACE FILE ---
$(cat "$trace_file")"

  local output
  output=$(codex exec --dangerously-bypass-approvals-and-sandbox "$prompt" 2>/dev/null) || {
    echo "FAIL $basename (codex error)"
    return 1
  }

  echo "$output" > "$result_file"

  if python3 -c "import json; json.load(open('$result_file'))" 2>/dev/null; then
    echo "OK   $basename"
  else
    # Try to extract JSON from output
    python3 -c "
import json, re, sys
text = open('$result_file').read().strip()
if text.startswith('\`\`\`'):
    text = re.sub(r'^\`\`\`(?:json)?\s*', '', text)
    text = re.sub(r'\s*\`\`\`\s*$', '', text)
m = re.search(r'\{[\s\S]*\}', text)
if m:
    d = json.loads(m.group())
    json.dump(d, open('$result_file', 'w'), indent=2)
    sys.exit(0)
sys.exit(1)
" 2>/dev/null && echo "OK   $basename (extracted)" || {
      echo "BAD  $basename (invalid JSON)"
      rm -f "$result_file"
      return 1
    }
  fi
}

export -f eval_trace
export RESULTS_DIR PROMPT_FILE

total=$(ls "$TRACES_DIR"/*.md 2>/dev/null | wc -l)
done_before=$(ls "$RESULTS_DIR"/*.json 2>/dev/null | wc -l)
echo "=== Meta-Judge Parallel (GPT-5.4 via Codex, ${MAX_PARALLEL}x) ==="
echo "Traces: $total | Already done: $done_before | Remaining: $((total - done_before))"
echo ""

# Run in parallel using xargs
ls "$TRACES_DIR"/*.md | xargs -P "$MAX_PARALLEL" -I{} bash -c 'eval_trace "$@"' _ {}

echo ""
echo "=== Done ==="
done_after=$(ls "$RESULTS_DIR"/*.json 2>/dev/null | wc -l)
echo "Completed: $done_after / $total"

# Aggregate
python3 aggregate.py
