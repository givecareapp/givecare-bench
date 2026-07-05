"""Comparative Failure Mode (CFM) extraction module.

Reads the authored CFM catalog (delivery/comparative_failure_modes.yaml) and a
scan's per_run.jsonl, then emits the ``comparative_failure_modes`` +
``model_profiles`` sections for the artifact-v2 payload.

No scores, no ranks, no composite anywhere.

Public API
----------
    from delivery.build_cfm import build_cfm_section

    section = build_cfm_section(
        scan_path=Path("results/safety_care_scan/<timestamp>/per_run.jsonl"),
    )
    # section["schema"] == "cfm/v1"
    # section["comparative_failure_modes"] == {"safety": [...], "care": [...]}
    # section["model_profiles"] == [...]

CLI
---
    python -m delivery.build_cfm --scan <path> --out <path>

    Gated on a fresh strict-QA stamp (VISION.md: no side doors) — the scan
    must have gone through the fail-closed publish chain
    (``invisiblebench.publish`` / ``scripts/publish.sh``) first, which writes
    ``data/leaderboard/.qa-stamp`` recording the scan's content hash right
    after strict QA passes. ``--unsafe-debug-bypass`` skips the gate for
    deliberate debugging only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from invisiblebench.utils.io import load_jsonl  # noqa: E402

DEFAULT_CATALOG = REPO_ROOT / "delivery" / "comparative_failure_modes.yaml"
QA_STAMP_FILENAME = ".qa-stamp"
DEFAULT_QA_STAMP = REPO_ROOT / "data" / "leaderboard" / QA_STAMP_FILENAME

# Maximum evidence entries per CFM (diversity across models/scenarios preferred).
_MAX_EVIDENCE = 5
# Maximum contrast entries per CFM.
_MAX_CONTRASTS = 3
# Minimum eligible runs for a model×CFM cell to be "sufficient_n".
_SUFFICIENT_N = 5
# Maximum notable exposures per model profile.
_MAX_NOTABLE = 5


# ---------------------------------------------------------------------------
# Wilson score interval (for layer=="safety" / claim-bearing CFMs only)
# ---------------------------------------------------------------------------

def _wilson_ci(occurrences: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion with ``n`` trials.

    Returns (lo, hi) clamped to [0, 1].  Returns (0.0, 1.0) for n == 0.
    """
    if n == 0:
        return (0.0, 1.0)
    p = occurrences / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    lo = max(0.0, centre - half)
    hi = min(1.0, centre + half)
    return (lo, hi)


# ---------------------------------------------------------------------------
# Catalog loading
# ---------------------------------------------------------------------------

def _load_catalog(catalog_path: Path) -> list[dict[str, Any]]:
    """Load and return the list of CFM definitions from the YAML catalog."""
    with open(catalog_path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    cfms: list[dict[str, Any]] = doc.get("comparative_failure_modes", [])
    retired = [cfm.get("id", "<unknown>") for cfm in cfms if "status" in cfm]
    if retired:
        ids = ", ".join(retired)
        raise ValueError(
            f"{catalog_path} uses retired CFM status fields for: {ids}. "
            "Use calibration_status/not_claim_ready metadata instead."
        )
    return cfms


# ---------------------------------------------------------------------------
# Eligibility + occurrence helpers
# ---------------------------------------------------------------------------

def _run_eligible_for_cfm(row: dict[str, Any], source_blindspots: list[str], source_checks: list[str]) -> bool:
    """Return True if this scan row is eligible for the given CFM.

    Eligible when:
    - ANY source_check mode_id is eligible (``eligible == True``) in mode_results, OR
    - ANY source_blindspot key has a non-null value (True or False) in blindspot_profile.
    """
    mode_index: dict[str, dict[str, Any]] = {
        mr["mode_id"]: mr for mr in row.get("mode_results", [])
    }
    for check_id in source_checks:
        mr = mode_index.get(check_id)
        if mr and mr.get("eligible", False):
            return True

    bp: dict[str, Any] = row.get("blindspot_profile") or {}
    for flag in source_blindspots:
        if bp.get(flag) is not None:  # True or False, not null
            return True

    return False


def _theme_occurred(row: dict[str, Any], source_blindspots: list[str], source_checks: list[str]) -> bool:
    """Return True if the failure mode occurred in this run.

    Occurred when:
    - ANY source_blindspot key is True in blindspot_profile, OR
    - ANY source_check mode_id has verdict == "FAIL" in mode_results.
    """
    bp: dict[str, Any] = row.get("blindspot_profile") or {}
    for flag in source_blindspots:
        if bp.get(flag) is True:
            return True

    mode_index: dict[str, dict[str, Any]] = {
        mr["mode_id"]: mr for mr in row.get("mode_results", [])
    }
    for check_id in source_checks:
        mr = mode_index.get(check_id)
        if mr and mr.get("verdict") == "FAIL":
            return True

    return False


# ---------------------------------------------------------------------------
# Evidence extraction
# ---------------------------------------------------------------------------

def _extract_fail_evidence(
    row: dict[str, Any],
    source_checks: list[str],
    model: str,
) -> list[dict[str, Any]]:
    """Extract evidence entries from FAILing source_checks in this row."""
    entries: list[dict[str, Any]] = []
    for mr in row.get("mode_results", []):
        if mr.get("mode_id") not in source_checks:
            continue
        if mr.get("verdict") != "FAIL":
            continue
        for ev in mr.get("evidence", []):
            entries.append(
                {
                    "model": model,
                    "scenario_id": row.get("scenario_id", ""),
                    "transcript_path": row.get("transcript_path"),
                    "quote": ev.get("quote") or ev.get("span") or "",
                    "turn_index": ev.get("turn") if "turn" in ev else None,
                    "severity": mr.get("severity"),
                    "rationale_code": mr.get("rationale_code"),
                }
            )
    return entries


def _diverse_evidence(
    all_entries: list[dict[str, Any]], max_entries: int
) -> list[dict[str, Any]]:
    """Select up to ``max_entries`` evidence entries with model/scenario diversity.

    Strategy: round-robin over (model, scenario_id) pairs until quota filled.
    """
    if not all_entries:
        return []

    # Group by (model, scenario_id)
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for e in all_entries:
        key = (e["model"], e["scenario_id"])
        buckets[key].append(e)

    keys = list(buckets.keys())
    result: list[dict[str, Any]] = []
    idx = 0
    while len(result) < max_entries and any(buckets[k] for k in keys):
        key = keys[idx % len(keys)]
        if buckets[key]:
            result.append(buckets[key].pop(0))
        idx += 1
    return result


# ---------------------------------------------------------------------------
# Contrast detection
# ---------------------------------------------------------------------------

def _find_contrasts(
    eligible_rows: list[dict[str, Any]],
    occurred_set: set[tuple[str, str]],
    source_checks: list[str,],
    max_contrasts: int,
) -> list[dict[str, Any]]:
    """Find contrast pairs: same scenario_id, one model fails the CFM, one holds.

    A contrast pair requires:
    - failing_model: theme_occurred == True
    - holding_model: CFM eligible but theme_occurred == False
    """
    # Index rows by scenario_id → list of rows
    by_scenario: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible_rows:
        by_scenario[row["scenario_id"]].append(row)

    contrasts: list[dict[str, Any]] = []
    seen_scenarios: set[str] = set()

    for scenario_id, rows in sorted(by_scenario.items()):
        if len(contrasts) >= max_contrasts:
            break

        failing = [r for r in rows if (r["model"], scenario_id) in occurred_set]
        holding = [r for r in rows if (r["model"], scenario_id) not in occurred_set]

        if not failing or not holding:
            continue

        # Prefer a unique scenario (no duplicates)
        if scenario_id in seen_scenarios:
            continue

        fail_row = failing[0]
        hold_row = holding[0]

        # Pull a fail quote from the failing model's source_check evidence
        fail_quote: str | None = None
        for mr in fail_row.get("mode_results", []):
            if mr.get("mode_id") in source_checks and mr.get("verdict") == "FAIL":
                ev_list = mr.get("evidence", [])
                if ev_list:
                    fail_quote = ev_list[0].get("quote") or ev_list[0].get("span")
                    break

        # Pull a hold quote if any evidence exists (may be PASS evidence)
        hold_quote: str | None = None
        for mr in hold_row.get("mode_results", []):
            if mr.get("mode_id") in source_checks and mr.get("evidence"):
                ev_list = mr.get("evidence", [])
                if ev_list:
                    hold_quote = ev_list[0].get("quote") or ev_list[0].get("span")
                    break

        contrasts.append(
            {
                "scenario_id": scenario_id,
                "failing_model": fail_row["model"],
                "holding_model": hold_row["model"],
                "fail_quote": fail_quote,
                "hold_quote": hold_quote,
                "analyst_summary": "",
            }
        )
        seen_scenarios.add(scenario_id)

    return contrasts


# ---------------------------------------------------------------------------
# Per-CFM computation
# ---------------------------------------------------------------------------

def _compute_cfm(
    cfm_def: dict[str, Any],
    rows: list[dict[str, Any]],
    model_names: list[str],
) -> dict[str, Any]:
    """Compute stats, evidence, and contrasts for one CFM.

    Returns the cfm object suitable for the output artifact.
    """
    cfm_id: str = cfm_def["id"]
    layer: str = cfm_def["layer"]  # "safety" | "care"
    source_blindspots: list[str] = cfm_def.get("source_blindspots", []) or []
    source_checks: list[str] = cfm_def.get("source_checks", []) or []

    # Known zero-check gap — current-contract metadata, no computed stats.
    if cfm_def.get("authored_checks") == 0:
        obj: dict[str, Any] = {
            "id": cfm_id,
            "title": cfm_def["title"],
            "dimension": cfm_def["dimension"],
            "layer": layer,
            "maturity": cfm_def["maturity"],
            "why_it_matters": cfm_def["why_it_matters"],
            "calibration_status": cfm_def.get("calibration_status", "not_claim_ready"),
            "directional": bool(cfm_def.get("directional", layer == "care")),
            "authored_checks": 0,
        }
        if cfm_def.get("related_dimensions"):
            obj["related_dimensions"] = cfm_def["related_dimensions"]
        return obj

    # --- Classify each row ---
    eligible_rows: list[dict[str, Any]] = []
    occurred_set: set[tuple[str, str]] = set()  # (model, scenario_id)

    for row in rows:
        model = row.get("model", row.get("model_id", "unknown"))
        if _run_eligible_for_cfm(row, source_blindspots, source_checks):
            eligible_rows.append(row)
            if _theme_occurred(row, source_blindspots, source_checks):
                occurred_set.add((model, row["scenario_id"]))

    # --- Field-level stats (across all models) ---
    total_eligible = len(eligible_rows)
    total_occurred = len(occurred_set)
    field_prevalence = total_occurred / total_eligible if total_eligible > 0 else 0.0

    field: dict[str, Any] = {
        "prevalence": round(field_prevalence, 4),
        "n": total_eligible,
    }
    if layer == "safety":
        lo, hi = _wilson_ci(total_occurred, total_eligible)
        field["ci"] = [round(lo, 4), round(hi, 4)]

    # --- Per-model stats ---
    by_model: dict[str, dict[str, Any]] = defaultdict(lambda: {"n": 0, "occurrences": 0})
    for row in eligible_rows:
        model = row.get("model", row.get("model_id", "unknown"))
        by_model[model]["n"] += 1
        if (model, row["scenario_id"]) in occurred_set:
            by_model[model]["occurrences"] += 1

    model_entries: list[dict[str, Any]] = []
    for model in model_names:
        cell = by_model.get(model, {"n": 0, "occurrences": 0})
        n = cell["n"]
        occ = cell["occurrences"]
        rate = round(occ / n, 4) if n > 0 else 0.0
        entry: dict[str, Any] = {
            "model": model,
            "occurrence_rate": rate,
            "n": n,
            "sufficient_n": n >= _SUFFICIENT_N,
        }
        if layer == "safety":
            lo, hi = _wilson_ci(occ, n)
            entry["ci"] = [round(lo, 4), round(hi, 4)]
        model_entries.append(entry)

    # --- Evidence (up to _MAX_EVIDENCE, diverse across models/scenarios) ---
    all_evidence: list[dict[str, Any]] = []
    for row in eligible_rows:
        model = row.get("model", row.get("model_id", "unknown"))
        all_evidence.extend(_extract_fail_evidence(row, source_checks, model))
    evidence = _diverse_evidence(all_evidence, _MAX_EVIDENCE)

    # --- Contrasts ---
    contrasts = _find_contrasts(eligible_rows, occurred_set, source_checks, _MAX_CONTRASTS)

    # --- Assemble CFM object ---
    obj = {
        "id": cfm_id,
        "title": cfm_def["title"],
        "dimension": cfm_def["dimension"],
        "layer": layer,
        "maturity": cfm_def["maturity"],
        "why_it_matters": cfm_def["why_it_matters"],
        "field": field,
        "models": model_entries,
        "evidence": evidence,
        "contrasts": contrasts,
    }
    if cfm_def.get("related_dimensions"):
        obj["related_dimensions"] = cfm_def["related_dimensions"]

    return obj


# ---------------------------------------------------------------------------
# Model profiles
# ---------------------------------------------------------------------------

def _build_model_profiles(
    cfm_objects: list[dict[str, Any]],
    model_names: list[str],
) -> list[dict[str, Any]]:
    """Build per-model notable exposure profiles.

    notable_exposures = CFMs where |model_rate - field_rate| is largest
    (top _MAX_NOTABLE by absolute delta; only sufficient_n cells included).
    No ordering key, no overall score.
    """
    # Collect all non-stub CFM objects
    live_cfms = [c for c in cfm_objects if "field" in c]

    profiles: list[dict[str, Any]] = []
    for model in model_names:
        deltas: list[tuple[float, str, float]] = []  # (abs_delta, theme_id, delta)
        for cfm in live_cfms:
            field_rate = cfm["field"]["prevalence"]
            for m_entry in cfm["models"]:
                if m_entry["model"] == model and m_entry["sufficient_n"]:
                    delta = m_entry["occurrence_rate"] - field_rate
                    deltas.append((abs(delta), cfm["id"], delta))

        deltas.sort(key=lambda x: x[0], reverse=True)
        notable = [
            {"theme_id": tid, "delta_vs_field": round(delta, 4)}
            for _, tid, delta in deltas[:_MAX_NOTABLE]
        ]
        profiles.append({"model": model, "notable_exposures": notable})

    return profiles


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_cfm_section(
    scan_path: Path | str,
    catalog_path: Path | str = DEFAULT_CATALOG,
) -> dict[str, Any]:
    """Build the CFM section for artifact-v2.

    Parameters
    ----------
    scan_path:
        Path to per_run.jsonl from a scan.
    catalog_path:
        Path to comparative_failure_modes.yaml (defaults to repo-local catalog).

    Returns
    -------
    dict with keys: schema, comparative_failure_modes, model_profiles.
    """
    scan_path = Path(scan_path)
    catalog_path = Path(catalog_path)

    rows = load_jsonl(scan_path)
    cfm_defs = _load_catalog(catalog_path)

    # Stable model name list (insertion-order of first encounter)
    seen: dict[str, None] = {}
    for row in rows:
        m = row.get("model", row.get("model_id", "unknown"))
        seen[m] = None
    model_names = list(seen)

    safety_cfms: list[dict[str, Any]] = []
    care_cfms: list[dict[str, Any]] = []

    for cfm_def in cfm_defs:
        obj = _compute_cfm(cfm_def, rows, model_names)
        if cfm_def["layer"] == "safety":
            safety_cfms.append(obj)
        else:
            care_cfms.append(obj)

    all_cfms = safety_cfms + care_cfms
    model_profiles = _build_model_profiles(all_cfms, model_names)

    return {
        "schema": "cfm/v1",
        "comparative_failure_modes": {
            "safety": safety_cfms,
            "care": care_cfms,
        },
        "model_profiles": model_profiles,
    }


# ---------------------------------------------------------------------------
# QA-stamp gate (VISION.md: no side doors)
#
# Mirrors delivery/sync_web_bench.py's _verify_qa_stamp pattern. That gate
# checks a leaderboard.json's bytes against a stamped hash; this one checks a
# scan's bytes, because build_cfm reads per_run.jsonl directly rather than the
# leaderboard artifact. Both gates read the SAME stamp file
# (data/leaderboard/.qa-stamp) — invisiblebench.publish writes it once, right
# after strict QA passes, with both the leaderboard hash (for sync_web_bench)
# and the scan path + hash (for build_cfm) recorded together.
# ---------------------------------------------------------------------------

class QAStampError(RuntimeError):
    """The CFM inputs have no fresh strict-QA stamp — refuse to emit a public
    artifact-v2 payload.

    VISION.md: no side doors. invisiblebench.publish (the fail-closed generate
    -> strict QA -> sync chain) writes data/leaderboard/.qa-stamp immediately
    after strict QA passes, recording both the QA'd leaderboard's bytes and
    the exact scan (path + content hash) that produced it. Calling
    `python -m delivery.build_cfm --scan ... --out ...` directly on a scan
    that was never through that chain — or a stamp that now points at a
    different scan — must fail loudly instead of silently shipping unvetted
    comparative-failure-mode claims to a public target.
    """


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _verify_qa_stamp(scan_path: Path, stamp_path: Path) -> None:
    if not stamp_path.exists():
        raise QAStampError(
            f"No QA stamp at {stamp_path}. Run the fail-closed publish chain "
            "(scripts/publish.sh or `python -m invisiblebench.publish`) against "
            "this scan first, or pass --unsafe-debug-bypass for a deliberate "
            "debug write."
        )

    try:
        stamp = json.loads(stamp_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise QAStampError(f"QA stamp at {stamp_path} is unreadable: {exc}") from exc

    stamped_scan_hash = stamp.get("scan_sha256")
    if not stamped_scan_hash:
        raise QAStampError(
            f"QA stamp at {stamp_path} has no scan_sha256 — it predates the "
            "scan-identity gate (or was written by an old invisiblebench.publish). "
            "Re-run the fail-closed publish chain to regenerate a compatible "
            "stamp, or pass --unsafe-debug-bypass for a deliberate debug write."
        )

    if not scan_path.exists():
        raise QAStampError(f"Scan file not found: {scan_path}")

    actual_hash = _sha256_bytes(scan_path.read_bytes())
    if stamped_scan_hash != actual_hash:
        raise QAStampError(
            f"QA stamp at {stamp_path} does not match {scan_path} (scan content "
            "hash mismatch) — this scan was never strict-QA'd, has changed since "
            "strict QA last passed, or is a different scan than the one the "
            "stamped leaderboard was generated from. Re-run the fail-closed "
            "publish chain against this scan, or pass --unsafe-debug-bypass for "
            "a deliberate debug write."
        )


def _print_unsafe_bypass_warning(scan_path: Path, out_path: Path) -> None:
    print(
        "\n".join(
            [
                "=" * 72,
                "UNSAFE DEBUG BYPASS — writing CFM artifact-v2 payload with NO fresh QA stamp.",
                f"  scan: {scan_path}",
                f"  out: {out_path}",
                "This skips the fail-closed publish gate (VISION.md: no side doors).",
                "Never use --unsafe-debug-bypass for a real publish — debugging only.",
                "=" * 72,
            ]
        ),
        file=sys.stderr,
    )


def build_and_write_cfm(
    scan_path: Path | str,
    out_path: Path | str,
    catalog_path: Path | str = DEFAULT_CATALOG,
    *,
    qa_stamp_path: Path | str = DEFAULT_QA_STAMP,
    unsafe_debug_bypass: bool = False,
) -> dict[str, Any]:
    """Build the CFM section and write it to ``out_path``.

    Gated on a fresh strict-QA stamp that was generated against this exact
    scan (VISION.md: no side doors) — the pure ``build_cfm_section()``
    computation above stays ungated (used directly by tests and any future
    read-only/--check tooling); only this write-to-disk path is gated, same
    split as sync_web_bench.py's project_leaderboard() vs sync_leaderboard().
    """
    scan_path = Path(scan_path)
    out_path = Path(out_path)
    qa_stamp_path = Path(qa_stamp_path)

    if unsafe_debug_bypass:
        _print_unsafe_bypass_warning(scan_path, out_path)
    else:
        _verify_qa_stamp(scan_path, qa_stamp_path)

    section = build_cfm_section(scan_path, catalog_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(section, indent=2))
    return section


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Build the CFM section (comparative_failure_modes + model_profiles) for artifact-v2."
    )
    parser.add_argument("--scan", required=True, help="Path to per_run.jsonl")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG), help="Path to CFM catalog YAML")
    parser.add_argument("--out", required=True, help="Output JSON path")
    parser.add_argument(
        "--qa-stamp",
        default=str(DEFAULT_QA_STAMP),
        help=(
            "Path to the strict-QA stamp written by invisiblebench.publish "
            f"(default: {DEFAULT_QA_STAMP})"
        ),
    )
    parser.add_argument(
        "--unsafe-debug-bypass",
        action="store_true",
        help=(
            "Skip the QA-stamp scan-identity gate and write anyway. Debugging "
            "only — never for a real publish (VISION.md: no side doors)."
        ),
    )
    args = parser.parse_args()

    try:
        section = build_and_write_cfm(
            Path(args.scan),
            Path(args.out),
            Path(args.catalog),
            qa_stamp_path=Path(args.qa_stamp),
            unsafe_debug_bypass=args.unsafe_debug_bypass,
        )
    except QAStampError as exc:
        print(f"build_cfm FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    out_path = Path(args.out)
    safety_cfms = section["comparative_failure_modes"]["safety"]
    care_cfms = section["comparative_failure_modes"]["care"]
    all_live = [c for c in safety_cfms + care_cfms if "field" in c]
    total_evidence = sum(len(c.get("evidence", [])) for c in all_live)
    total_contrasts = sum(len(c.get("contrasts", [])) for c in all_live)

    print(
        f"CFM section written to {out_path}: "
        f"{len(safety_cfms)} safety CFMs, {len(care_cfms)} care CFMs, "
        f"{total_evidence} evidence quotes, {total_contrasts} contrasts."
    )


if __name__ == "__main__":
    _cli()
