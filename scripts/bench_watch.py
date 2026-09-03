#!/usr/bin/env python3
"""Read-only OpenRouter release watcher for the gc-bench roster policy.

Owner rule (2026-09-03, ~/wiki/atlas/givecare-bench.md): evaluation is
event-driven. A scan runs only when a roster-eligible model or model version
is released, or when the benchmark standard itself changes (a scenario/check
version bump makes every model due for re-scan). Listening for releases is
periodic; scanning is not. Scans are paid and human-gated: this script
proposes, the owner approves elsewhere. The output stays a jagged profile,
never a rank.

This script never spends money, never runs a scan, and never calls
docket-emit. It only reads the public OpenRouter catalog (no API key) plus
local repo config, and writes a dated proposal under delivery/watch/.

Usage:
    uv run --frozen python scripts/bench_watch.py --propose

Reads:
  - benchmark/configs/roster.json      (the roster policy this lane enforces)
  - benchmark/benchmark_inventory.json (current standard/corpus version)
  - data/leaderboard/leaderboard.json  (last published scan's coverage + version)
  - https://openrouter.ai/api/v1/models (public catalog, no key required)

Writes:
  - delivery/watch/<YYYY-MM-DD>.json
  - delivery/watch/<YYYY-MM-DD>.md

Idempotent per day: re-running on the same UTC date recomputes and overwrites
that day's two files rather than accumulating duplicates.

Terminal output: the last non-empty stdout line is the rack token — DONE when
the proposal carries one or more candidates (new roster-eligible releases or
a standard-change re-scan), DECLINED when it carries none, BROKEN (preceded
by a FAILED_CHECK line) when a required read could not be trusted.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
ROSTER_PATH = REPO_ROOT / "benchmark" / "configs" / "roster.json"
INVENTORY_PATH = REPO_ROOT / "benchmark" / "benchmark_inventory.json"
LEADERBOARD_PATH = REPO_ROOT / "data" / "leaderboard" / "leaderboard.json"
WATCH_DIR = REPO_ROOT / "delivery" / "watch"

OPENROUTER_API = "https://openrouter.ai/api/v1/models"

# Kept in sync by hand with ~/agents/_skills/openrouter/openrouter.py's
# EXCLUDE list. Both filter the same public catalog down to genuine
# text-in/text-out chat models (drops image/audio/embedding/guard/
# moderation/code-only/-latest-alias/:free variants). Duplicated rather than
# imported so this script stays stdlib-only and behaves identically in tests
# and on atum, independent of the skill directory's presence or layout.
EXCLUDE = (
    "guard", "safety", "moderation", "embed", "tts", "whisper", "image",
    "vision", "-code", "coder", "-latest", ":free", "-build", "rerank", "ocr",
)

_VERSION_RE = re.compile(r"\d+(?:\.\d+)*")


class WatchError(RuntimeError):
    """A bounded, reportable failure. (check, error) becomes FAILED_CHECK text."""

    def __init__(self, check: str, error: str) -> None:
        super().__init__(f"{check}: {error}")
        self.check = check
        self.error = error


# ---------------------------------------------------------------------------
# Catalog access and filtering
# ---------------------------------------------------------------------------


def fetch_catalog() -> list[dict[str, Any]]:
    """Fetch the public OpenRouter model catalog. No API key required.

    A separate, overridable entry point so tests supply a fixture catalog
    without touching the network.
    """
    try:
        with urllib.request.urlopen(OPENROUTER_API, timeout=30) as resp:
            payload = json.load(resp)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise WatchError("catalog_fetch", str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise WatchError("catalog_fetch", f"malformed catalog JSON: {exc}") from exc
    data = payload.get("data")
    if not isinstance(data, list):
        raise WatchError("catalog_fetch", "catalog response missing a 'data' list")
    return data


def is_text_chat(model: dict[str, Any]) -> bool:
    """True for genuine text-in/text-out chat models."""
    arch = model.get("architecture") or {}
    outs = arch.get("output_modalities") or []
    ins = arch.get("input_modalities") or []
    if outs and outs != ["text"]:
        return False
    if ins and "text" not in ins:
        return False
    model_id = model.get("id", "")
    return not any(token in model_id.lower() for token in EXCLUDE)


def price_per_m(model: dict[str, Any]) -> tuple[float, float]:
    pricing = model.get("pricing") or {}
    prompt = float(pricing.get("prompt") or 0) * 1e6
    completion = float(pricing.get("completion") or 0) * 1e6
    return prompt, completion


def family_stem(model_id: str) -> str:
    """Normalize a model id to its version-agnostic family.

    ``anthropic/claude-opus-4.8`` and ``anthropic/claude-opus-5.0`` both
    reduce to ``anthropic/claude-opus-#``, so a same-family id with a
    different version number can be spotted as "a new version of a scanned
    model" without a hardcoded version list. Used only to widen a match
    within one provider/family, never to invent a match across unrelated
    model names.
    """
    provider, _, slug = model_id.partition("/")
    slug = slug.split(":", 1)[0]
    return f"{provider}/{_VERSION_RE.sub('#', slug)}"


# ---------------------------------------------------------------------------
# Local repo reads
# ---------------------------------------------------------------------------


def load_json(path: Path, check: str) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise WatchError(check, f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise WatchError(check, f"malformed JSON in {path}: {exc}") from exc


def load_roster() -> dict[str, Any]:
    roster = load_json(ROSTER_PATH, "roster_schema")
    rules = roster.get("rules")
    if not isinstance(rules, dict):
        raise WatchError("roster_schema", "roster.json missing a 'rules' object")
    for key in ("product_models", "requested_by_field", "providers_in_scope"):
        if not isinstance(rules.get(key), list):
            raise WatchError("roster_schema", f"rules.{key} must be a list")
    if "settle_days" not in roster:
        raise WatchError("roster_schema", "roster.json missing 'settle_days'")
    if "scanned" not in roster:
        raise WatchError("roster_schema", "roster.json missing 'scanned'")
    return roster


def load_scanned(roster: dict[str, Any]) -> dict[str, str]:
    """model_id -> leaderboard_version, from roster.json's 'scanned' record."""
    scanned: dict[str, str] = {}
    for entry in roster.get("scanned", []):
        model_id = entry.get("model_id")
        version = entry.get("leaderboard_version")
        if model_id and version:
            scanned[model_id] = version
    return scanned


def current_standard_version() -> str:
    inventory = load_json(INVENTORY_PATH, "standard_version")
    version = inventory.get("benchmark_version")
    if not version:
        raise WatchError("standard_version", "benchmark_inventory.json missing 'benchmark_version'")
    return version


def published_leaderboard_version() -> tuple[str | None, str | None]:
    """(benchmark_version, generated_at) of the current published leaderboard.

    (None, None) when no leaderboard has been generated yet — not an error;
    a first-ever watch has nothing published to compare against.
    """
    if not LEADERBOARD_PATH.exists():
        return None, None
    leaderboard = load_json(LEADERBOARD_PATH, "leaderboard_read")
    meta = leaderboard.get("scan_metadata") or {}
    return meta.get("benchmark_version"), meta.get("generated_at")


def estimate_cost_per_model() -> float | str:
    """Average per-model actual cost from the last published scan's source_merge.

    Used as a same-size-scan cost estimate for one new candidate model.
    Returns "unknown" when no cost accounting is on record for the current
    leaderboard (see benchmark/tests/unit/test_cost_accounting.py for the
    accounting shape this reads).
    """
    if not LEADERBOARD_PATH.exists():
        return "unknown"
    leaderboard = load_json(LEADERBOARD_PATH, "cost_estimate")
    sources = leaderboard.get("scan_metadata", {}).get("source_merge", {}).get("sources", [])
    costs = [
        s["actual_cost_usd"] for s in sources if isinstance(s.get("actual_cost_usd"), (int, float))
    ]
    if not costs:
        return "unknown"
    return round(sum(costs) / len(costs), 2)


def last_watch_date(today: str) -> str | None:
    if not WATCH_DIR.exists():
        return None
    dates = sorted(p.stem for p in WATCH_DIR.glob("*.json") if p.stem != today)
    return dates[-1] if dates else None


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------


def _base_id(model_id: str) -> str:
    """Strip a catalog variant suffix (e.g. ``:batch``, ``:free``) from an id."""
    return model_id.split(":", 1)[0]


def _scanned_family_latest_created(
    catalog_by_id: dict[str, dict[str, Any]], scanned: dict[str, str]
) -> tuple[dict[str, int], list[str]]:
    """The most recent ``created`` timestamp per scanned model's family.

    Looked up from the *current* catalog fetch, not stored in roster.json —
    a scanned model can be re-priced or briefly delisted, so its own id is
    the only trustworthy source for "how recent is what we already scanned."
    Families whose scanned id is absent from the current catalog are
    reported back (second return value) rather than guessed at.
    """
    latest: dict[str, int] = {}
    missing: list[str] = []
    for model_id in scanned:
        base = _base_id(model_id)
        model = catalog_by_id.get(model_id) or catalog_by_id.get(base)
        if model is None:
            missing.append(model_id)
            continue
        stem = family_stem(model_id)
        created = model.get("created") or 0
        latest[stem] = max(created, latest.get(stem, 0))
    return latest, missing


def eligible_candidates(
    catalog: list[dict[str, Any]],
    roster: dict[str, Any],
    scanned: dict[str, str],
    now: dt.datetime,
) -> tuple[list[dict[str, Any]], list[str]]:
    """New OpenRouter releases that qualify under roster.json's rules.

    A release qualifies when its provider is in scope, it is a genuine
    text-chat model, it has settled for ``settle_days`` (avoids scanning a
    release that may still be re-priced or re-routed), it is not already a
    scanned id or a variant SKU of one (e.g. ``:batch`` of an already-scanned
    id), and it matches ``product_models`` or is a *newer* release in an
    already-scanned family (same provider and id with version numbers
    stripped, e.g. ``claude-opus-4.8`` and ``claude-opus-5.0`` both reduce to
    ``claude-opus-#`` — but only the one created after the scanned sibling
    qualifies, never an older release that merely shares the family name).

    Returns ``(candidates, notes)`` — notes flag scanned families the current
    catalog no longer lists, where a version bump can't be detected.
    """
    providers_in_scope = set(roster["rules"]["providers_in_scope"])
    product_models = set(roster["rules"]["product_models"])
    scanned_bases = {_base_id(mid) for mid in scanned}
    settle_days = roster.get("settle_days", 7)

    catalog_by_id = {m.get("id"): m for m in catalog if m.get("id")}
    family_latest_created, missing_families = _scanned_family_latest_created(catalog_by_id, scanned)
    notes = [
        f"scanned model {mid} is no longer listed in the OpenRouter catalog; "
        "a new version of it cannot be auto-detected until it (or a "
        "successor) reappears"
        for mid in missing_families
    ]

    candidates = []
    for model in catalog:
        model_id = model.get("id", "")
        if not model_id or ":" in model_id:
            # A colon suffix (:batch, :free, ...) is a pricing SKU of the
            # base model, not a separate release — the base id is the
            # candidate to propose, never its variants.
            continue
        if model_id in scanned or _base_id(model_id) in scanned_bases:
            continue
        provider = model_id.split("/", 1)[0]
        if providers_in_scope and provider not in providers_in_scope:
            continue
        if not is_text_chat(model):
            continue

        created = model.get("created") or 0
        created_dt = dt.datetime.fromtimestamp(created, dt.UTC) if created else None
        if created_dt is None or (now - created_dt) < dt.timedelta(days=settle_days):
            continue

        if model_id in product_models:
            rule = "product_models"
        else:
            stem = family_stem(model_id)
            latest_scanned_created = family_latest_created.get(stem)
            if latest_scanned_created is not None and created > latest_scanned_created:
                rule = "new_version_of_scanned"
            else:
                continue

        pin, pout = price_per_m(model)
        candidates.append(
            {
                "model_id": model_id,
                "provider": provider,
                "created": created_dt.strftime("%Y-%m-%d"),
                "price_per_m_input_usd": round(pin, 4),
                "price_per_m_output_usd": round(pout, 4),
                "qualifying_rule": rule,
            }
        )
    candidates.sort(key=lambda c: c["model_id"])
    return candidates, notes


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in version.split(".") if p.isdigit())


def standard_change_candidates(
    scanned: dict[str, str],
    current_version: str,
    leaderboard_version: str | None,
) -> list[dict[str, Any]]:
    """Every scanned model, proposed for re-scan, when the standard moved on.

    Compares the repo's current corpus/checks version
    (benchmark_inventory.json) against the version stamped on the published
    leaderboard. A scenario/check version bump breaks cross-run
    comparability, so every previously scanned model becomes due again.
    """
    if leaderboard_version is None:
        return []
    if _version_tuple(current_version) <= _version_tuple(leaderboard_version):
        return []
    return [
        {
            "model_id": model_id,
            "provider": model_id.split("/", 1)[0],
            "created": None,
            "price_per_m_input_usd": None,
            "price_per_m_output_usd": None,
            "qualifying_rule": "standard_change",
            "note": (
                f"standard moved {leaderboard_version} -> {current_version}; "
                "re-scan required for comparability"
            ),
        }
        for model_id in sorted(scanned)
    ]


# ---------------------------------------------------------------------------
# Proposal assembly
# ---------------------------------------------------------------------------


def build_proposal(today: str, now: dt.datetime | None = None) -> dict[str, Any]:
    roster = load_roster()
    scanned = load_scanned(roster)
    now = now or dt.datetime.now(dt.UTC)

    current_version = current_standard_version()
    leaderboard_version, leaderboard_generated_at = published_leaderboard_version()

    catalog = fetch_catalog()
    new_candidates, family_notes = eligible_candidates(catalog, roster, scanned, now)
    change_candidates = standard_change_candidates(scanned, current_version, leaderboard_version)
    candidates = change_candidates + new_candidates

    cost_estimate = estimate_cost_per_model()
    for candidate in candidates:
        candidate["estimated_scan_cost_usd"] = cost_estimate

    notes = list(family_notes)
    top_n = roster["rules"].get("top_n_capability") or {}
    if not top_n.get("index") or top_n.get("n") is None:
        notes.append(
            "top_n_capability inactive: rules.top_n_capability.index and .n are not both "
            "set in roster.json, so this rule contributes no candidates until the owner "
            "fills them."
        )

    return {
        "watch_version": "1.0.0",
        "date": today,
        "roster_version": roster.get("roster_version"),
        "catalog_checked_at": now.isoformat(),
        "standard_change": {
            "detected": bool(change_candidates),
            "current_benchmark_version": current_version,
            "leaderboard_benchmark_version": leaderboard_version,
            "leaderboard_generated_at": leaderboard_generated_at,
        },
        "candidates": candidates,
        "notes": notes,
        "prior_watch_date": last_watch_date(today),
    }


def render_markdown(proposal: dict[str, Any]) -> str:
    lines = [f"# Bench watch — {proposal['date']}", ""]
    sc = proposal["standard_change"]
    if sc["detected"]:
        lines.append(
            f"**Standard changed**: benchmark_version moved "
            f"{sc['leaderboard_benchmark_version']} -> {sc['current_benchmark_version']}. "
            "Every scanned model needs a full re-scan for comparability."
        )
        lines.append("")

    if not proposal["candidates"]:
        since = proposal["prior_watch_date"] or "the first watch"
        lines.append(f"No roster-eligible release since {since}.")
    else:
        lines.append("| Model | Provider | Created | $/M in | $/M out | Est. scan cost | Rule |")
        lines.append("|---|---|---|---:|---:|---:|---|")
        for c in proposal["candidates"]:
            created = c.get("created") or "—"
            pin = c.get("price_per_m_input_usd")
            pout = c.get("price_per_m_output_usd")
            lines.append(
                f"| {c['model_id']} | {c['provider']} | {created} | "
                f"{pin if pin is not None else '—'} | "
                f"{pout if pout is not None else '—'} | "
                f"{c['estimated_scan_cost_usd']} | {c['qualifying_rule']} |"
            )

    for note in proposal.get("notes", []):
        lines.append("")
        lines.append(f"_{note}_")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_propose(now: dt.datetime | None = None) -> int:
    now = now or dt.datetime.now(dt.UTC)
    today = now.strftime("%Y-%m-%d")
    try:
        proposal = build_proposal(today, now=now)
    except WatchError as exc:
        print(f"FAILED_CHECK: {exc.check}: {exc.error}")
        print("BROKEN")
        return 1

    WATCH_DIR.mkdir(parents=True, exist_ok=True)
    json_path = WATCH_DIR / f"{today}.json"
    md_path = WATCH_DIR / f"{today}.md"
    json_path.write_text(json.dumps(proposal, indent=2) + "\n")
    md_path.write_text(render_markdown(proposal))

    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    if proposal["candidates"]:
        print(f"{len(proposal['candidates'])} roster-eligible candidate(s)")
        print("DONE")
    else:
        since = proposal["prior_watch_date"] or "the first watch"
        print(f"no roster-eligible release since {since}")
        print("DECLINED")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--propose", action="store_true", help="read-only: propose roster-eligible scan candidates"
    )
    args = parser.parse_args()
    if not args.propose:
        parser.print_help()
        sys.exit(2)
    sys.exit(run_propose())


if __name__ == "__main__":
    main()
