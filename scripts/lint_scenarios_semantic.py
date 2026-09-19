#!/usr/bin/env python3
"""Semantic corpus lint: does each scenario's text actually carry its cues?

Read-only. For every scenario, and for every check the scenario declares in
`eligible_modes` that has a `cue: {role: user}`, this asks the judge model
the check's cue question against each user turn and reports the strongest
signal found. A scenario whose declared check never fires its cue is an
authoring bug: the check will always resolve NOT_APPLICABLE in a real scan,
silently, no matter what the model under test does.

Requests carry only what exists at authoring time: `caregiver` (this turn),
`earlier_caregiver` (prior user turns in the scenario, across sessions in
turn-number order), and `earlier_assistant` (always empty — no assistant
turn has been generated yet). This mirrors `rules.build_request` with
`role="user"`, which is what a real scan sends for cue questions.

Contrast groups (`contrast_group`/`contrast_variable`) get a second view: a
per-check table across the group's members, and a `contrast_not_separated`
flag. Which check a variant is "about" is read structurally, from the
declared difference between the variant's and the anchor's own
`eligible_modes` (declaring or dropping a check id, not string-matching
`contrast_variable`, which is free text and not reliably keyword-bearing
across the corpus):

  - a check the anchor declares and the variant drops (a "cue removed"
    variant): expects anchor >= high and variant < high. Flagged if the
    anchor is itself weak (nothing there to remove) or the variant still
    scores >= high (removal did not work).
  - a check the variant declares and the anchor does not (a "cue added"
    variant, e.g. an ambiguous anchor made explicit): expects variant >=
    high. Flagged if it doesn't clear high.
  - a check both declare (a style/surface variant, e.g. SMS shorthand,
    that must preserve the same cue): expects the two to land on the same
    side of `high`. Flagged only when they disagree; two shared checks
    that both stay weak (a broad, rarely-cued catch-all check) are
    consistent, not unseparated, and a lone weak score is already caught
    by that scenario's own weak_cue/no_cue flag.
  - a check neither declares is not compared.

Every request is cached on disk by its content hash, so a rerun after the
corpus changes only pays for turns that actually changed.
"""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from invisiblebench.evaluation.check_registry import load_checks
from invisiblebench.evaluation.rules import build_request, cue_key, input_hash
from invisiblebench.models.scan import Check, Thresholds
from invisiblebench.models.scenario import Scenario
from invisiblebench.utils.benchmark_inventory import collect_scenario_paths

DEFAULT_CACHE_DIR = REPO_ROOT / ".cache" / "semantic-lint"


# --------------------------------------------------------------------------
# Loading and request-building
# --------------------------------------------------------------------------


@dataclass
class LoadedScenario:
    path: Path
    scenario: Scenario
    eligible_modes: list[str]

    @property
    def scenario_id(self) -> str:
        return self.scenario.scenario_id

    @property
    def contrast_group(self) -> str | None:
        return self.scenario.contrast_group

    @property
    def contrast_variable(self) -> str | None:
        return self.scenario.contrast_variable


def load_scenario(path: Path) -> LoadedScenario:
    raw = json.loads(path.read_text())
    scenario = Scenario.from_dict(raw, source_path=str(path))
    eligible_modes = list(raw.get("eligible_modes") or [])
    return LoadedScenario(path=path, scenario=scenario, eligible_modes=eligible_modes)


def user_cue_checks(checks: dict[str, Check], eligible_modes: list[str]) -> list[Check]:
    """Checks this scenario declares that ask a yes/no question of a user turn."""
    return sorted(
        (
            checks[check_id]
            for check_id in eligible_modes
            if check_id in checks
            and checks[check_id].cue is not None
            and checks[check_id].cue.role == "user"
        ),
        key=lambda check: check.id,
    )


def user_transcript(scenario: Scenario) -> list[dict[str, Any]]:
    """The scenario's user turns as the `rules` transcript shape, turn-number order."""
    turns = [
        {"role": "user", "turn": turn.turn_number, "content": turn.user_message}
        for turn in scenario.all_turns
    ]
    return sorted(turns, key=lambda turn: turn["turn"])


# --------------------------------------------------------------------------
# Cached judge calls
# --------------------------------------------------------------------------


@dataclass
class JudgeCache:
    """Answers cue questions, reading/writing one JSON file per request hash."""

    client: Any
    model: str
    cache_dir: Path
    requests_made: int = 0
    input_tokens: int = 0

    def answer(self, request: dict[str, Any]) -> dict[str, float]:
        if not request["questions"]:
            return {}
        digest = input_hash(request)
        cache_path = self.cache_dir / f"{digest}.json"
        if cache_path.exists():
            return json.loads(cache_path.read_text())["nouls"]
        response = self.client.ask(
            model=self.model, state=request["state"], questions=request["questions"]
        )
        self.requests_made += 1
        self.input_tokens += int(response.get("input_tokens", 0))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(response, sort_keys=True))
        return response["nouls"]


def cue_probabilities(
    scenario: Scenario, checks: list[Check], cache: JudgeCache
) -> dict[str, dict[int, float]]:
    """check.id -> {turn_number: cue probability} over every user turn."""
    result: dict[str, dict[int, float]] = {check.id: {} for check in checks}
    if not checks:
        return result
    transcript = user_transcript(scenario)
    for entry in transcript:
        turn_number = entry["turn"]
        request = build_request(checks, transcript, "user", turn_number)
        answers = cache.answer(request)
        for check in checks:
            probability = answers.get(cue_key(check))
            if probability is not None:
                result[check.id][turn_number] = probability
    return result


def strongest(per_turn: dict[int, float]) -> tuple[float, int | None]:
    if not per_turn:
        return 0.0, None
    turn = max(per_turn, key=lambda number: per_turn[number])
    return per_turn[turn], turn


def flag_for(probability: float, thresholds: Thresholds) -> str | None:
    if probability <= thresholds.low:
        return "no_cue"
    if probability < thresholds.high:
        return "weak_cue"
    return None


# --------------------------------------------------------------------------
# Report assembly
# --------------------------------------------------------------------------


@dataclass
class ScenarioResult:
    loaded: LoadedScenario
    own_check_ids: set[str]
    per_turn: dict[str, dict[int, float]]  # covers own_check_ids plus, for
    # grouped scenarios, every check any group member declares


def build_scenario_results(
    loaded_scenarios: list[LoadedScenario], checks: dict[str, Check], cache: JudgeCache
) -> list[ScenarioResult]:
    groups: dict[str, list[LoadedScenario]] = {}
    for loaded in loaded_scenarios:
        if loaded.contrast_group:
            groups.setdefault(loaded.contrast_group, []).append(loaded)

    own_ids: dict[str, set[str]] = {}
    for loaded in loaded_scenarios:
        own = user_cue_checks(checks, loaded.eligible_modes)
        own_ids[loaded.scenario_id] = {check.id for check in own}

    group_union_checks: dict[str, list[Check]] = {}
    for group_name, members in groups.items():
        ids: set[str] = set()
        for member in members:
            ids |= own_ids[member.scenario_id]
        group_union_checks[group_name] = sorted(
            (checks[check_id] for check_id in ids), key=lambda check: check.id
        )

    results = []
    for loaded in loaded_scenarios:
        query_checks = (
            group_union_checks[loaded.contrast_group]
            if loaded.contrast_group
            else user_cue_checks(checks, loaded.eligible_modes)
        )
        per_turn = cue_probabilities(loaded.scenario, query_checks, cache)
        results.append(
            ScenarioResult(
                loaded=loaded, own_check_ids=own_ids[loaded.scenario_id], per_turn=per_turn
            )
        )
    return results


def scenario_report(result: ScenarioResult, thresholds: Thresholds) -> dict[str, Any]:
    checks = []
    for check_id in sorted(result.own_check_ids):
        probability, turn = strongest(result.per_turn.get(check_id, {}))
        flag = flag_for(probability, thresholds)
        entry: dict[str, Any] = {
            "check_id": check_id,
            "max_probability": probability,
            "max_turn": turn,
        }
        if flag:
            entry["flag"] = flag
        checks.append(entry)
    path = result.loaded.path
    try:
        path = path.relative_to(REPO_ROOT)
    except ValueError:
        pass  # outside the repo (e.g. a test fixture) -- report it as given
    return {
        "scenario_id": result.loaded.scenario_id,
        "path": str(path),
        "checks": checks,
    }


ANCHOR = "anchor"


def contrast_report(
    results: list[ScenarioResult], thresholds: Thresholds
) -> dict[str, dict[str, Any]]:
    by_group: dict[str, list[ScenarioResult]] = {}
    for result in results:
        group = result.loaded.contrast_group
        if group:
            by_group.setdefault(group, []).append(result)

    report: dict[str, dict[str, Any]] = {}
    for group_name, members in sorted(by_group.items()):
        anchor = next(
            (m for m in members if m.loaded.contrast_variable == ANCHOR), None
        )
        union_check_ids = sorted({c for m in members for c in m.per_turn})
        table_rows = []
        for check_id in union_check_ids:
            row = {"check_id": check_id}
            for member in members:
                probability, turn = strongest(member.per_turn.get(check_id, {}))
                row[member.loaded.scenario_id] = {
                    "contrast_variable": member.loaded.contrast_variable,
                    "max_probability": probability,
                    "max_turn": turn,
                }
            table_rows.append(row)

        flags: list[dict[str, Any]] = []
        if anchor is not None:
            for member in members:
                if member is anchor:
                    continue
                for check_id in union_check_ids:
                    in_anchor = check_id in anchor.own_check_ids
                    in_variant = check_id in member.own_check_ids
                    if in_anchor == in_variant and not (in_anchor and in_variant):
                        continue  # neither side declares it
                    anchor_prob, _ = strongest(anchor.per_turn.get(check_id, {}))
                    variant_prob, _ = strongest(member.per_turn.get(check_id, {}))
                    separated = True
                    if in_anchor and in_variant:
                        # Both declare the check: the cue only needs to agree on
                        # which side of `high` it lands, not both clear it. Two
                        # scenarios that share a broad, rarely-cued check (e.g. a
                        # catch-all like scope.ai-disclosure) and both score near
                        # zero on it are correctly consistent, not unseparated;
                        # a scenario scoring low on its own declared check is
                        # already caught by the per-scenario weak_cue/no_cue flag.
                        expectation = "preserved"
                        separated = (anchor_prob >= thresholds.high) == (
                            variant_prob >= thresholds.high
                        )
                    elif in_anchor:
                        expectation = "removed"
                        separated = (
                            anchor_prob >= thresholds.high and variant_prob < thresholds.high
                        )
                    else:
                        expectation = "added"
                        separated = variant_prob >= thresholds.high
                    if not separated:
                        flags.append(
                            {
                                "variant_scenario_id": member.loaded.scenario_id,
                                "check_id": check_id,
                                "expectation": expectation,
                                "anchor_probability": anchor_prob,
                                "variant_probability": variant_prob,
                                "flag": "contrast_not_separated",
                            }
                        )

        report[group_name] = {
            "anchor": anchor.loaded.scenario_id if anchor else None,
            "members": [m.loaded.scenario_id for m in members],
            "table": table_rows,
            "flags": flags,
        }
    return report


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def render_text(
    scenario_reports: list[dict[str, Any]],
    contrast: dict[str, dict[str, Any]],
    *,
    requests_made: int,
    input_tokens: int,
    cost_usd: float,
) -> str:
    lines = ["Semantic cue lint"]
    has_flags = False
    for report in scenario_reports:
        flagged = [c for c in report["checks"] if c.get("flag")]
        if not flagged:
            continue
        has_flags = True
        lines.append(f"\n{report['scenario_id']} ({report['path']})")
        for check in flagged:
            turn = check["max_turn"] if check["max_turn"] is not None else "-"
            lines.append(
                f"  {check['flag']:>10}  {check['check_id']:<32} "
                f"max={check['max_probability']:.2f} turn={turn}"
            )
    if not has_flags:
        lines.append("  no weak_cue or no_cue flags")

    lines.append("\nContrast groups")
    if not contrast:
        lines.append("  no contrast-grouped scenarios")
    for group_name, entry in sorted(contrast.items()):
        lines.append(f"\n{group_name} (anchor: {entry['anchor'] or 'MISSING'})")
        for row in entry["table"]:
            cells = []
            for scenario_id in entry["members"]:
                cell = row.get(scenario_id)
                if cell is None:
                    continue
                cells.append(f"{scenario_id}={cell['max_probability']:.2f}")
            lines.append(f"  {row['check_id']:<32} " + "  ".join(cells))
        for flag in entry["flags"]:
            lines.append(
                f"  contrast_not_separated  {flag['variant_scenario_id']} / "
                f"{flag['check_id']} ({flag['expectation']}): "
                f"anchor={flag['anchor_probability']:.2f} "
                f"variant={flag['variant_probability']:.2f}"
            )

    lines.append(
        f"\nRequests: {requests_made}  Input tokens: {input_tokens}  Cost: ${cost_usd:.4f}"
    )
    return "\n".join(lines)


def any_flags(scenario_reports: list[dict[str, Any]], contrast: dict[str, dict[str, Any]]) -> bool:
    for report in scenario_reports:
        if any(check.get("flag") for check in report["checks"]):
            return True
    for entry in contrast.values():
        if entry["flags"]:
            return True
    return False


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def select_scenarios(
    *, include_private: bool, limit: int | None, scenario_filter: str | None
) -> list[Path]:
    paths = collect_scenario_paths(include_confidential=include_private)
    if scenario_filter:
        paths = [p for p in paths if scenario_filter in p.stem or scenario_filter in str(p)]
    if limit is not None:
        paths = paths[:limit]
    return paths


def execute(
    paths: list[Path],
    *,
    client: Any,
    model: str,
    cache_dir: Path,
    max_cost_usd: float | None,
    as_json: bool,
    strict: bool,
) -> int:
    """Run the lint over `paths` with an already-built judge client and print the report.

    Split from `main()` so tests can inject a fake client without touching
    argv, environment credentials, or the network.
    """
    from invisiblebench.api.client import cost_tracker

    cost_tracker.reset(max_cost_usd=max_cost_usd)
    cache = JudgeCache(client=client, model=model, cache_dir=cache_dir)

    checks = load_checks()
    loaded_scenarios = [load_scenario(path) for path in paths]
    results = build_scenario_results(loaded_scenarios, checks, cache)
    thresholds = Thresholds()

    scenario_reports = [scenario_report(result, thresholds) for result in results]
    contrast = contrast_report(results, thresholds)

    if as_json:
        payload = {
            "scenarios": scenario_reports,
            "contrast_groups": contrast,
            "requests_made": cache.requests_made,
            "input_tokens": cache.input_tokens,
            "cost_usd": cost_tracker.total,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(
            render_text(
                scenario_reports,
                contrast,
                requests_made=cache.requests_made,
                input_tokens=cache.input_tokens,
                cost_usd=cost_tracker.total,
            )
        )

    if strict and any_flags(scenario_reports, contrast):
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-private", action="store_true", help="Also lint confidential scenarios"
    )
    parser.add_argument("--json", action="store_true", help="Print the report as JSON")
    parser.add_argument("--strict", action="store_true", help="Exit 1 if any flag is found")
    parser.add_argument("--limit", type=int, default=None, help="Lint at most N scenarios")
    parser.add_argument(
        "--scenario", default=None, help="Only scenarios whose id or path contains this text"
    )
    parser.add_argument("--model", default=None, help="Judge model id (default: SystemOne default)")
    parser.add_argument(
        "--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help="On-disk response cache"
    )
    parser.add_argument(
        "--max-cost-usd", type=float, default=None, help="Abort once this cost is reached"
    )
    args = parser.parse_args()

    try:
        paths = select_scenarios(
            include_private=args.include_private, limit=args.limit, scenario_filter=args.scenario
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not paths:
        print("No scenarios matched", file=sys.stderr)
        return 2

    from invisiblebench.api.typesafe import DEFAULT_JUDGE_MODEL, SystemOneClient

    return execute(
        paths,
        client=SystemOneClient(),
        model=args.model or DEFAULT_JUDGE_MODEL,
        cache_dir=args.cache_dir,
        max_cost_usd=args.max_cost_usd,
        as_json=args.json,
        strict=args.strict,
    )


if __name__ == "__main__":
    raise SystemExit(main())
