#!/usr/bin/env bash
# Post a benchmark update as a GitHub Discussion.
#
# Usage:
#   ./scripts/post_discussion.sh "Title here" body.md              # Post from file
#   ./scripts/post_discussion.sh "Title here" body.md --dry-run    # Preview
#   ./scripts/post_discussion.sh autoresearch                      # Shortcut: post autoresearch report
#   ./scripts/post_discussion.sh benchmark results/run_*/all_results.json  # Shortcut: benchmark run summary
#
# Requires: gh CLI authenticated, discussions enabled on repo.

set -euo pipefail

REPO="givecareapp/givecare-bench"
CATEGORY_ID="DIC_kwDOP_ckO84C4DuN"  # "Show and tell"
DRY_RUN=false

# Parse flags
ARGS=()
for arg in "$@"; do
    case $arg in
        --dry-run) DRY_RUN=true ;;
        *) ARGS+=("$arg") ;;
    esac
done

usage() {
    echo "Usage:"
    echo "  $0 \"Title\" body.md [--dry-run]"
    echo "  $0 autoresearch [--dry-run]"
    echo "  $0 benchmark <results.json> [--dry-run]"
    exit 1
}

[ ${#ARGS[@]} -lt 1 ] && usage

# ── Shortcuts ─────────────────────────────────────────────────

case "${ARGS[0]}" in
    autoresearch)
        REPORT="autoresearch/REPORT.md"
        LOG="autoresearch/experiment_log.md"
        [ ! -f "$REPORT" ] && echo "Error: $REPORT not found" && exit 1

        DATE=$(grep "Date" "$REPORT" | head -1 | sed 's/.*: //' || date +%Y-%m-%d)
        TITLE="AutoResearch: scenario differentiation — ${DATE}"

        BODY="> Automated report from autoresearch campaign.

$(cat "$REPORT")"

        if [ -f "$LOG" ]; then
            BODY="$BODY

---

<details>
<summary>Full experiment log</summary>

$(cat "$LOG")

</details>"
        fi
        ;;

    benchmark)
        RESULTS="${ARGS[1]:-}"
        [ -z "$RESULTS" ] && echo "Error: provide results JSON path" && exit 1
        [ ! -f "$RESULTS" ] && echo "Error: $RESULTS not found" && exit 1

        # Generate summary from results
        SUMMARY=$(python3 -c "
import json, sys
with open('$RESULTS') as f:
    data = json.load(f)

results = data if isinstance(data, list) else data.get('results', data.get('scenarios', []))
if not results:
    print('No results found'); sys.exit(1)

# Group by model
models = {}
for r in results:
    m = r.get('model', r.get('model_name', '?'))
    if m not in models:
        models[m] = {'scores': [], 'fails': 0, 'total': 0}
    models[m]['total'] += 1
    s = r.get('overall_score', 0)
    models[m]['scores'].append(s)
    if r.get('status') == 'fail' or r.get('hard_fail'):
        models[m]['fails'] += 1

print('| Model | Mean | Hard Fails | Scenarios |')
print('|-------|:----:|:----------:|:---------:|')
for m, d in sorted(models.items(), key=lambda x: -sum(x[1]['scores'])/max(len(x[1]['scores']),1)):
    mean = sum(d['scores']) / max(len(d['scores']), 1)
    print(f'| {m} | {mean:.3f} | {d[\"fails\"]}/{d[\"total\"]} | {d[\"total\"]} |')
" 2>&1)

        MODEL_COUNT=$(echo "$SUMMARY" | grep -c "^|" | tail -1)
        DATE=$(date +%Y-%m-%d)
        TITLE="Benchmark run: ${MODEL_COUNT} models — ${DATE}"

        BODY="> Full benchmark run results.

## Results

$SUMMARY

**Source:** \`$RESULTS\`"
        ;;

    *)
        # Generic: title + body file
        TITLE="${ARGS[0]}"
        BODY_FILE="${ARGS[1]:-}"
        [ -z "$BODY_FILE" ] && usage
        [ ! -f "$BODY_FILE" ] && echo "Error: $BODY_FILE not found" && exit 1
        BODY=$(cat "$BODY_FILE")
        ;;
esac

# ── Append git context ────────────────────────────────────────

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "detached")
COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BODY="$BODY

---

**Branch:** \`$BRANCH\` | **Commit:** \`$COMMIT\` | **Posted:** $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# ── Post or preview ──────────────────────────────────────────

if [ "$DRY_RUN" = true ]; then
    echo "=== DRY RUN ==="
    echo "Title: $TITLE"
    echo "Body: $(echo "$BODY" | wc -c | tr -d ' ') chars"
    echo ""
    echo "$BODY" | head -50
    echo "..."
    exit 0
fi

REPO_ID=$(gh api graphql -f query='{
  repository(owner: "givecareapp", name: "givecare-bench") { id }
}' --jq '.data.repository.id')

RESULT=$(gh api graphql -f query='
mutation($repoId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
  createDiscussion(input: {
    repositoryId: $repoId
    categoryId: $categoryId
    title: $title
    body: $body
  }) {
    discussion {
      url
      number
    }
  }
}' -f repoId="$REPO_ID" -f categoryId="$CATEGORY_ID" -f title="$TITLE" -f body="$BODY")

URL=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['createDiscussion']['discussion']['url'])")
echo "Posted: $URL"
