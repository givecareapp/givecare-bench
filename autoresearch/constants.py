"""Locked experiment parameters. DO NOT MODIFY during experiment runs.

Changes to these constants invalidate all prior results and require
a full baseline recalculation. Edit only between experiment campaigns.
"""

# ── Probe Models ──────────────────────────────────────────────
# 3 models spanning the full performance range.
# Best performer, worst performer, middle.
PROBE_MODELS = [
    "anthropic/claude-opus-4.5",       # Best: 0% fail rate, highest scores
    "google/gemini-3-pro-preview",     # Worst: lowest mean, highest fail rate
    "openai/gpt-5-mini",              # Middle: median performer, different failure modes
]

# ── Thresholds ────────────────────────────────────────────────
SPREAD_THRESHOLD_COMMIT = 0.20   # Minimum spread to commit an improvement
SPREAD_THRESHOLD_TARGET = 0.30   # Goal spread per scenario

# ── Budget ────────────────────────────────────────────────────
MAX_TURNS_PER_SCENARIO = 15      # Diminishing returns beyond this
MAX_EXPERIMENTS_PER_SCENARIO = 3  # Move on after 3 attempts

# ── Scoring ───────────────────────────────────────────────────
SCORER_TEMPERATURE = 0.0         # Deterministic scoring for reproducibility
SCORER_CACHE_ENABLED = False     # Disable cache during experiments (need fresh scores)
