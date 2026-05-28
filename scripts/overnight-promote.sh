#!/usr/bin/env bash
# overnight-promote.sh — Batch probe staged scenarios and stage passing ones
# for morning human review.
#
# For each staged scenario (up to --max-scenarios):
#   1. Run the campaign probe phase (3 probe models)
#   2. If spread metric passes guardrails: copy to benchmark/review/
#   3. If fails: skip, log reason
#
# Promotions go to benchmark/review/ for human review, NOT benchmark/scenarios/.
#
# Usage:
#   ./scripts/overnight-promote.sh                    # default: up to 50 scenarios
#   ./scripts/overnight-promote.sh --max-scenarios 10 # limit batch size
#   ./scripts/overnight-promote.sh --dry-run          # print what would run, no bench calls

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGING_DIR="$REPO_ROOT/benchmark/staging"
REVIEW_DIR="$REPO_ROOT/benchmark/review"
TSV_LOG="$REPO_ROOT/data/overnight-campaign.tsv"
COMPUTE_SPREAD="$REPO_ROOT/internal/autoresearch/_compute_spread.py"

# Probe models — same compact set used by autoresearch campaigns
PROBE_MODELS="Claude Opus 4.6,Claude Sonnet 4.5,GPT-5 Mini"

# Guardrails (probe-level defaults from program.md)
MIN_MODELS=3
MIN_MEAN=0.2
MAX_MEAN=0.95

# Defaults
MAX_SCENARIOS=50
DRY_RUN=false
RUN_TIMEOUT=660

# ── Parse args ──────────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --max-scenarios)
            MAX_SCENARIOS="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --timeout)
            RUN_TIMEOUT="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            echo "Usage: $0 [--max-scenarios N] [--dry-run] [--timeout SECONDS]" >&2
            exit 1
            ;;
    esac
done

# ── Preflight ───────────────────────────────────────────────────────────────

if [[ ! -d "$STAGING_DIR" ]]; then
    echo "ERROR: staging directory not found: $STAGING_DIR" >&2
    exit 1
fi

mkdir -p "$REVIEW_DIR"
mkdir -p "$(dirname "$TSV_LOG")"

# Initialize TSV log if it doesn't exist
if [[ ! -f "$TSV_LOG" ]]; then
    printf 'timestamp\tscenario_id\tcategory\tsubcategory\tstatus\tspread\tmean\tn_models\treason\trun_dir\n' > "$TSV_LOG"
fi

echo "overnight-promote: starting batch probe"
echo "  Staging dir:    $STAGING_DIR"
echo "  Review dir:     $REVIEW_DIR"
echo "  Max scenarios:  $MAX_SCENARIOS"
echo "  Probe models:   $PROBE_MODELS"
echo "  Dry run:        $DRY_RUN"
echo ""

# ── Collect staged scenarios ────────────────────────────────────────────────

mapfile -t SCENARIO_FILES < <(find "$STAGING_DIR" -name '*.json' -type f | sort)
TOTAL_STAGED="${#SCENARIO_FILES[@]}"
echo "Found $TOTAL_STAGED staged scenarios"
echo ""

if [[ "$TOTAL_STAGED" -eq 0 ]]; then
    echo "No staged scenarios to process."
    exit 0
fi

# ── Process scenarios ───────────────────────────────────────────────────────

PROCESSED=0
STAGED_FOR_REVIEW=0
FAILED=0
SKIPPED=0

for SCENARIO_FILE in "${SCENARIO_FILES[@]}"; do
    if [[ "$PROCESSED" -ge "$MAX_SCENARIOS" ]]; then
        break
    fi

    # Extract scenario metadata
    SCENARIO_ID="$(python3 -c "import json; d=json.load(open('$SCENARIO_FILE')); print(d.get('scenario_id', d.get('id', 'unknown')))")"
    CATEGORY="$(python3 -c "import json; d=json.load(open('$SCENARIO_FILE')); print(d.get('category', 'unknown'))")"

    # Compute subcategory from path (e.g., safety/crisis, empathy/grief)
    REL_PATH="${SCENARIO_FILE#"$STAGING_DIR/"}"
    SUBCATEGORY="$(dirname "$REL_PATH" | tr '/' '_')"

    TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    PROCESSED=$((PROCESSED + 1))

    echo "[$PROCESSED/$MAX_SCENARIOS] $SCENARIO_ID ($CATEGORY/$SUBCATEGORY)"

    if $DRY_RUN; then
        echo "  DRY RUN: would probe with $PROBE_MODELS"
        echo "  File: $SCENARIO_FILE"
        echo ""
        SKIPPED=$((SKIPPED + 1))
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$TIMESTAMP" "$SCENARIO_ID" "$CATEGORY" "$SUBCATEGORY" \
            "dry_run" "0" "0" "0" "dry run" "" >> "$TSV_LOG"
        continue
    fi

    # Step 1: Run bench probe on this single scenario
    # Copy scenario temporarily into benchmark/scenarios/ to make bench see it,
    # run the probe, then remove it. This avoids modifying staging in place.
    TEMP_SCENARIO_DIR="$REPO_ROOT/benchmark/scenarios/_overnight_probe"
    mkdir -p "$TEMP_SCENARIO_DIR"
    cp "$SCENARIO_FILE" "$TEMP_SCENARIO_DIR/"

    SCENARIO_BASENAME="$(basename "$SCENARIO_FILE" .json)"
    RUN_DIR=""
    BENCH_OUTPUT=""
    BENCH_EXIT=0

    BENCH_OUTPUT="$(timeout "${RUN_TIMEOUT}s" \
        uv run bench \
        -m "$PROBE_MODELS" \
        -s "$SCENARIO_ID" \
        -y --detailed \
        2>&1)" || BENCH_EXIT=$?

    # Clean up temporary scenario
    rm -rf "$TEMP_SCENARIO_DIR"

    if [[ "$BENCH_EXIT" -ne 0 ]]; then
        REASON="bench exited with code $BENCH_EXIT"
        echo "  FAILED: $REASON"
        FAILED=$((FAILED + 1))
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$TIMESTAMP" "$SCENARIO_ID" "$CATEGORY" "$SUBCATEGORY" \
            "error" "0" "0" "0" "$REASON" "" >> "$TSV_LOG"
        echo ""
        continue
    fi

    # Extract run directory from output
    RUN_DIR="$(echo "$BENCH_OUTPUT" | grep -oP 'results/run_\S+' | head -1 || true)"

    if [[ -z "$RUN_DIR" ]]; then
        REASON="no run directory found in bench output"
        echo "  FAILED: $REASON"
        FAILED=$((FAILED + 1))
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$TIMESTAMP" "$SCENARIO_ID" "$CATEGORY" "$SUBCATEGORY" \
            "error" "0" "0" "0" "$REASON" "" >> "$TSV_LOG"
        echo ""
        continue
    fi

    RUN_DIR_ABS="$REPO_ROOT/$RUN_DIR"

    # Step 2: Compute spread and check guardrails
    SPREAD_OUTPUT="$(python3 "$COMPUTE_SPREAD" \
        --run-dir "$RUN_DIR_ABS" \
        --scenario "$SCENARIO_ID" \
        --label "overnight-$SCENARIO_ID" \
        --output "/tmp/overnight-spread-${SCENARIO_BASENAME}.json" \
        --min-models "$MIN_MODELS" \
        --min-mean "$MIN_MEAN" \
        --max-mean "$MAX_MEAN" \
        2>&1)" || true

    SPREAD_JSON="/tmp/overnight-spread-${SCENARIO_BASENAME}.json"

    if [[ ! -f "$SPREAD_JSON" ]]; then
        REASON="spread computation failed"
        echo "  FAILED: $REASON"
        FAILED=$((FAILED + 1))
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$TIMESTAMP" "$SCENARIO_ID" "$CATEGORY" "$SUBCATEGORY" \
            "error" "0" "0" "0" "$REASON" "$RUN_DIR" >> "$TSV_LOG"
        echo ""
        continue
    fi

    # Parse spread results
    GUARDRAILS_OK="$(python3 -c "import json; d=json.load(open('$SPREAD_JSON')); print('true' if d.get('guardrails',{}).get('ok') else 'false')")"
    SPREAD_VAL="$(python3 -c "import json; d=json.load(open('$SPREAD_JSON')); print(d.get('spread', 0))")"
    MEAN_VAL="$(python3 -c "import json; d=json.load(open('$SPREAD_JSON')); print(d.get('mean', 0))")"
    N_MODELS_VAL="$(python3 -c "import json; d=json.load(open('$SPREAD_JSON')); print(d.get('n_models', 0))")"
    GUARDRAIL_REASONS="$(python3 -c "import json; d=json.load(open('$SPREAD_JSON')); print('; '.join(d.get('guardrails',{}).get('reasons',[])))")"

    if [[ "$GUARDRAILS_OK" == "true" ]]; then
        # Step 2a: Copy to review directory, preserving category structure
        REVIEW_SUBDIR="$REVIEW_DIR/$CATEGORY"
        if [[ "$SUBCATEGORY" != "$CATEGORY" && "$SUBCATEGORY" != "." ]]; then
            REVIEW_SUBDIR="$REVIEW_DIR/$SUBCATEGORY"
        fi
        mkdir -p "$REVIEW_SUBDIR"
        cp "$SCENARIO_FILE" "$REVIEW_SUBDIR/"

        echo "  PASSED: spread=$SPREAD_VAL mean=$MEAN_VAL models=$N_MODELS_VAL"
        echo "  Staged for review: $REVIEW_SUBDIR/$(basename "$SCENARIO_FILE")"
        STAGED_FOR_REVIEW=$((STAGED_FOR_REVIEW + 1))
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$TIMESTAMP" "$SCENARIO_ID" "$CATEGORY" "$SUBCATEGORY" \
            "review" "$SPREAD_VAL" "$MEAN_VAL" "$N_MODELS_VAL" "passed guardrails" "$RUN_DIR" >> "$TSV_LOG"
    else
        # Step 2b: Skip, log reason
        echo "  FAILED guardrails: $GUARDRAIL_REASONS"
        echo "  spread=$SPREAD_VAL mean=$MEAN_VAL models=$N_MODELS_VAL"
        FAILED=$((FAILED + 1))
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$TIMESTAMP" "$SCENARIO_ID" "$CATEGORY" "$SUBCATEGORY" \
            "failed" "$SPREAD_VAL" "$MEAN_VAL" "$N_MODELS_VAL" "$GUARDRAIL_REASONS" "$RUN_DIR" >> "$TSV_LOG"
    fi

    # Clean up temp spread JSON
    rm -f "$SPREAD_JSON"
    echo ""
done

# ── Summary ─────────────────────────────────────────────────────────────────

echo "============================================"
echo "overnight-promote: batch complete"
echo "  Total staged:        $TOTAL_STAGED"
echo "  Processed:           $PROCESSED"
echo "  Staged for review:   $STAGED_FOR_REVIEW"
echo "  Failed guardrails:   $FAILED"
if $DRY_RUN; then
    echo "  Skipped (dry run):   $SKIPPED"
fi
echo "  Results log:         $TSV_LOG"
echo "  Review dir:          $REVIEW_DIR/"
echo "============================================"

if [[ "$STAGED_FOR_REVIEW" -gt 0 ]]; then
    echo ""
    echo "Review staged scenarios before promoting to benchmark/scenarios/."
    echo "Files in benchmark/review/ are NOT part of the active benchmark."
fi
