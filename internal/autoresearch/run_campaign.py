#!/usr/bin/env python3
"""Autoresearch-style runner for single-scenario benchmark campaigns.

This adapts the keep/discard loop from karpathy/autoresearch to benchmark
scenario work:
- one mutable file (the current scenario JSON)
- fixed evaluator (bench + spread extractor)
- a probe search loop with automatic keep/discard logging
- a broader promotion gate before landing scenario changes
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import yaml

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent.parent
PROGRAM_PATH = THIS_DIR / "program.md"
RESULTS_HEADER = ["commit", "score", "status", "description", "notes"]
RUN_DIR_RE = re.compile(r"results/run_[^\s]+")

if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from _compute_spread import GuardrailConfig, compute_spread_summary, load_run_rows  # noqa: E402


@dataclass(frozen=True)
class CampaignConfig:
    campaign_id: str
    title: str
    mutable_file: Path
    scenario_filter: str
    probe_models: tuple[str, ...]
    promotion_models: tuple[str, ...]
    direction: str
    results_log: Path
    artifacts_dir: Path
    branch_prefix: str
    probe_guardrails: GuardrailConfig
    promotion_guardrails: GuardrailConfig
    run_timeout_seconds: int
    promotion_note: str


@dataclass(frozen=True)
class PhaseResult:
    phase: str
    command: list[str]
    run_dir: Path | None
    artifact_path: Path
    summary: dict[str, Any]


def _read_program_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text()
    if not text.startswith("---\n"):
        raise ValueError(f"{path} is missing YAML front matter")
    try:
        _, rest = text.split("---\n", 1)
        front_matter, body = rest.split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError(f"{path} has invalid YAML front matter delimiters") from exc
    data = yaml.safe_load(front_matter) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} front matter must be a mapping")
    return data, body


def load_campaign_config(path: Path = PROGRAM_PATH) -> CampaignConfig:
    data, body = _read_program_frontmatter(path)
    title = str(data.get("title") or _extract_title(body) or "AutoResearch campaign")
    mutable_file = REPO_ROOT / str(data["mutable_file"])
    results_log = REPO_ROOT / str(data.get("results_log", "internal/autoresearch/results.tsv"))
    artifacts_dir = REPO_ROOT / str(data.get("artifacts_dir", "internal/autoresearch/results"))
    probe = data.get("probe_guardrails") or {}
    promotion = data.get("promotion_guardrails") or {}
    return CampaignConfig(
        campaign_id=str(data["campaign_id"]),
        title=title,
        mutable_file=mutable_file,
        scenario_filter=str(data["scenario_filter"]),
        probe_models=tuple(str(item) for item in data["probe_models"]),
        promotion_models=tuple(str(item) for item in data["promotion_models"]),
        direction=str(data.get("direction", "higher")),
        results_log=results_log,
        artifacts_dir=artifacts_dir,
        branch_prefix=str(data.get("branch_prefix", "autoresearch")),
        probe_guardrails=GuardrailConfig(
            min_models=int(probe.get("min_models", 3)),
            min_mean=float(probe.get("min_mean", 0.2)),
            max_mean=float(probe.get("max_mean", 0.95)),
            forbid_errors=bool(probe.get("forbid_errors", True)),
            forbid_all_fail=bool(probe.get("forbid_all_fail", True)),
            forbid_all_hard_fail=bool(probe.get("forbid_all_hard_fail", True)),
        ),
        promotion_guardrails=GuardrailConfig(
            min_models=int(promotion.get("min_models", 5)),
            min_mean=float(promotion.get("min_mean", 0.2)),
            max_mean=float(promotion.get("max_mean", 0.95)),
            forbid_errors=bool(promotion.get("forbid_errors", True)),
            forbid_all_fail=bool(promotion.get("forbid_all_fail", True)),
            forbid_all_hard_fail=bool(promotion.get("forbid_all_hard_fail", True)),
        ),
        run_timeout_seconds=int(data.get("run_timeout_seconds", 660)),
        promotion_note=str(data.get("promotion_note", "Promotion review required before merge.")),
    )


def _extract_title(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _git(*args: str, check: bool = True) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if check and process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or process.stdout.strip() or f"git {' '.join(args)} failed")
    return process.stdout.strip()


def _tracked_changes() -> list[str]:
    output = _git("status", "--porcelain", "--untracked-files=no")
    paths: list[str] = []
    for line in output.splitlines():
        if not line:
            continue
        raw = line[3:]
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        paths.append(raw)
    return paths


def _ensure_clean_tracked_tree() -> None:
    changes = _tracked_changes()
    if changes:
        raise RuntimeError("tracked working tree is dirty; commit, stash, or revert changes before running setup")


def _ensure_only_mutable_file_changed(config: CampaignConfig) -> None:
    changes = _tracked_changes()
    if not changes:
        raise RuntimeError(f"no tracked changes found; edit {config.mutable_file.relative_to(REPO_ROOT)} first")
    allowed = config.mutable_file.relative_to(REPO_ROOT).as_posix()
    extra = sorted(path for path in changes if path != allowed)
    if extra:
        joined = ", ".join(extra)
        raise RuntimeError(f"candidate must change only {allowed}; found additional tracked changes: {joined}")


def _current_branch() -> str:
    return _git("rev-parse", "--abbrev-ref", "HEAD")


def _short_head() -> str:
    return _git("rev-parse", "--short", "HEAD")


def _ensure_results_log(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(RESULTS_HEADER)


def _read_results_log(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [dict(row) for row in reader]


def _sanitize_tsv(value: str) -> str:
    return value.replace("\t", " ").replace("\n", " ").strip()


def _append_results_row(path: Path, row: dict[str, str]) -> None:
    _ensure_results_log(path)
    with path.open("a", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow([_sanitize_tsv(row.get(column, "")) for column in RESULTS_HEADER])


def _frontier_row(rows: list[dict[str, str]], direction: str) -> dict[str, str] | None:
    keeps = [row for row in rows if row.get("status") == "keep"]
    if not keeps:
        return None
    reverse = direction == "higher"
    return sorted(keeps, key=lambda row: float(row.get("score") or 0.0), reverse=reverse)[0]


def _branch_name(config: CampaignConfig, tag: str) -> str:
    return f"{config.branch_prefix}/{tag}"


def _build_bench_command(models: Sequence[str], scenario_filter: str) -> list[str]:
    return ["uv", "run", "bench", "-m", ",".join(models), "-s", scenario_filter, "-y", "--detailed"]


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _artifact_path(config: CampaignConfig, phase: str, label: str) -> Path:
    safe_label = re.sub(r"[^a-zA-Z0-9._-]+", "-", label).strip("-") or phase
    return config.artifacts_dir / f"{_timestamp()}_{phase}_{safe_label}.json"


def _extract_run_dir(output: str) -> Path | None:
    match = RUN_DIR_RE.search(output)
    if not match:
        return None
    return REPO_ROOT / match.group(0)


def _run_phase(
    config: CampaignConfig,
    phase: str,
    label: str,
    models: Sequence[str],
    guardrails: GuardrailConfig,
    *,
    dry_run: bool = False,
    scenario_filter: str | None = None,
) -> PhaseResult:
    scenario = scenario_filter or config.scenario_filter
    command = _build_bench_command(models, scenario)
    artifact_path = _artifact_path(config, phase, label)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)

    if dry_run:
        summary = {
            "label": label,
            "scenario": scenario,
            "dry_run": True,
            "command": command,
            "models": list(models),
        }
        artifact_path.write_text(json.dumps(summary, indent=2))
        return PhaseResult(phase, command, None, artifact_path, summary)

    try:
        process = subprocess.run(
            command,
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=config.run_timeout_seconds,
            check=False,
        )
        output = process.stdout
    except subprocess.TimeoutExpired:
        summary = {
            "label": label,
            "scenario": scenario,
            "error": f"command timed out after {config.run_timeout_seconds} seconds",
            "command": command,
            "models": list(models),
        }
        artifact_path.write_text(json.dumps(summary, indent=2))
        return PhaseResult(phase, command, None, artifact_path, summary)

    run_dir = _extract_run_dir(output)
    if process.returncode != 0 or run_dir is None:
        summary = {
            "label": label,
            "scenario": scenario,
            "error": "bench command failed before a run directory was emitted",
            "exit_code": process.returncode,
            "command": command,
            "models": list(models),
            "output_tail": output.splitlines()[-20:],
        }
        artifact_path.write_text(json.dumps(summary, indent=2))
        return PhaseResult(phase, command, run_dir, artifact_path, summary)

    summary = compute_spread_summary(load_run_rows(run_dir), scenario, label, guardrails)
    summary["phase"] = phase
    summary["command"] = command
    summary["run_dir"] = run_dir.relative_to(REPO_ROOT).as_posix()
    summary["models_requested"] = list(models)
    artifact_path.write_text(json.dumps(summary, indent=2))
    return PhaseResult(phase, command, run_dir, artifact_path, summary)


def _print_phase_result(result: PhaseResult) -> None:
    summary = result.summary
    print(f"Phase:      {result.phase}")
    print(f"Command:    {' '.join(result.command)}")
    if result.run_dir is not None:
        print(f"Run dir:    {result.run_dir.relative_to(REPO_ROOT)}")
    print(f"Artifact:   {result.artifact_path.relative_to(REPO_ROOT)}")
    if summary.get("dry_run"):
        print("Status:     DRY RUN")
        return
    if summary.get("error"):
        print(f"Status:     ERROR — {summary['error']}")
        return
    print(f"Spread:     {summary['spread']:.3f}")
    print(f"Mean:       {summary['mean']:.3f}")
    print(f"Guardrails: {'OK' if summary['guardrails']['ok'] else 'FAIL'}")
    for reason in summary["guardrails"]["reasons"]:
        print(f"  - {reason}")


def _candidate_description(description: str) -> str:
    cleaned = _sanitize_tsv(description)
    if not cleaned:
        raise RuntimeError("description must not be empty")
    return cleaned


def _create_candidate_commit(config: CampaignConfig, description: str) -> str:
    _ensure_only_mutable_file_changed(config)
    relative_mutable = config.mutable_file.relative_to(REPO_ROOT).as_posix()
    _git("add", relative_mutable)
    _git("commit", "-m", f"autoresearch: {description}")
    return _short_head()


def _revert_candidate_commit() -> None:
    _git("reset", "--hard", "HEAD~1")


def _notes_for_result(result: PhaseResult) -> str:
    summary = result.summary
    if summary.get("error"):
        return f"artifact={result.artifact_path.relative_to(REPO_ROOT)}; error={summary['error']}"
    run_note = f"run={summary.get('run_dir', '?')}"
    mean_note = f"mean={summary['mean']:.3f}"
    guardrail_note = (
        "guardrails=ok"
        if summary["guardrails"]["ok"]
        else "guardrails=" + "; ".join(summary["guardrails"]["reasons"])
    )
    return (
        f"artifact={result.artifact_path.relative_to(REPO_ROOT)}; {run_note}; {mean_note}; {guardrail_note}"
    )


def cmd_setup(args: argparse.Namespace) -> int:
    config = load_campaign_config()
    _ensure_clean_tracked_tree()
    branch = _branch_name(config, args.tag)
    existing = _git("branch", "--list", branch)
    if existing:
        raise RuntimeError(f"branch already exists: {branch}")
    _git("switch", "-c", branch)
    _ensure_results_log(config.results_log)
    print(f"Created branch: {branch}")
    print(f"Campaign:       {config.title}")
    print(f"Mutable file:   {config.mutable_file.relative_to(REPO_ROOT)}")
    print(f"Results log:    {config.results_log.relative_to(REPO_ROOT)}")
    print("Next step:      uv run python internal/autoresearch/run_campaign.py baseline")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    config = load_campaign_config()
    rows = _read_results_log(config.results_log)
    frontier = _frontier_row(rows, config.direction)
    print(f"Campaign:      {config.title}")
    print(f"Branch:        {_current_branch()}")
    print(f"Mutable file:  {config.mutable_file.relative_to(REPO_ROOT)}")
    print(f"Scenario:      {config.scenario_filter}")
    print(f"Probe models:  {', '.join(config.probe_models)}")
    print(f"Promo models:  {', '.join(config.promotion_models)}")
    print(f"Tracked diff:  {len(_tracked_changes())} tracked path(s)")
    if frontier:
        print(
            "Frontier:      "
            f"{frontier['score']} @ {frontier['commit']} ({frontier['description']})"
        )
    else:
        print("Frontier:      none yet — run baseline first")
    return 0


def cmd_probe_run(args: argparse.Namespace) -> int:
    config = load_campaign_config()
    result = _run_phase(
        config,
        phase="probe",
        label=args.label or "probe-run",
        models=config.probe_models,
        guardrails=config.probe_guardrails,
        dry_run=args.dry_run,
        scenario_filter=args.scenario,
    )
    _print_phase_result(result)
    return 0 if not result.summary.get("error") else 1


def cmd_baseline(args: argparse.Namespace) -> int:
    config = load_campaign_config()
    if _tracked_changes():
        raise RuntimeError("baseline must run on a clean tracked tree")
    _ensure_results_log(config.results_log)
    existing = _read_results_log(config.results_log)
    if _frontier_row(existing, config.direction) and not args.force:
        raise RuntimeError("baseline already recorded; use --force to record another baseline row")

    result = _run_phase(
        config,
        phase="probe",
        label="baseline",
        models=config.probe_models,
        guardrails=config.probe_guardrails,
    )
    _print_phase_result(result)
    score = float(result.summary.get("spread", 0.0)) if not result.summary.get("error") else 0.0
    status = "keep" if not result.summary.get("error") and result.summary["guardrails"]["ok"] else "crash"
    _append_results_row(
        config.results_log,
        {
            "commit": _short_head(),
            "score": f"{score:.3f}",
            "status": status,
            "description": "baseline",
            "notes": _notes_for_result(result),
        },
    )
    return 0 if status == "keep" else 1


def cmd_experiment(args: argparse.Namespace) -> int:
    config = load_campaign_config()
    description = _candidate_description(args.description)
    rows = _read_results_log(config.results_log)
    frontier = _frontier_row(rows, config.direction)
    if frontier is None:
        raise RuntimeError("no baseline/frontier found; run baseline first")

    candidate_commit = _create_candidate_commit(config, description)
    result = _run_phase(
        config,
        phase="probe",
        label=candidate_commit,
        models=config.probe_models,
        guardrails=config.probe_guardrails,
    )
    _print_phase_result(result)

    summary = result.summary
    score = float(summary.get("spread", 0.0)) if not summary.get("error") else 0.0
    frontier_score = float(frontier["score"])
    improved = score > frontier_score if config.direction == "higher" else score < frontier_score
    keep = not summary.get("error") and summary["guardrails"]["ok"] and improved
    status = "keep" if keep else ("crash" if summary.get("error") else "discard")
    notes = _notes_for_result(result)

    _append_results_row(
        config.results_log,
        {
            "commit": candidate_commit,
            "score": f"{score:.3f}",
            "status": status,
            "description": description,
            "notes": notes,
        },
    )

    if keep:
        print(f"Kept candidate {candidate_commit}: spread improved from {frontier_score:.3f} to {score:.3f}")
        print(f"Next step: run promotion before merge — {config.promotion_note}")
        return 0

    _revert_candidate_commit()
    if summary.get("error"):
        print(f"Discarded crashed candidate {candidate_commit} and reverted to prior frontier")
    elif not summary["guardrails"]["ok"]:
        print(f"Discarded {candidate_commit}: guardrails failed and reverted to prior frontier")
    else:
        print(
            f"Discarded {candidate_commit}: spread {score:.3f} did not beat frontier {frontier_score:.3f}; reverted"
        )
    return 1


def cmd_promote(args: argparse.Namespace) -> int:
    config = load_campaign_config()
    if _tracked_changes():
        raise RuntimeError("promotion must run on a clean tracked tree")
    result = _run_phase(
        config,
        phase="promotion",
        label=_short_head(),
        models=config.promotion_models,
        guardrails=config.promotion_guardrails,
    )
    _print_phase_result(result)
    if result.summary.get("error") or not result.summary["guardrails"]["ok"]:
        print("Promotion gate failed. Do not merge this scenario revision yet.")
        return 1
    print("Promotion gate passed.")
    print("Manual follow-up: spot-check strongest vs weakest transcripts before landing to main.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup = subparsers.add_parser("setup", help="create an autoresearch branch and initialize the results log")
    setup.add_argument("--tag", required=True)
    setup.set_defaults(func=cmd_setup)

    status = subparsers.add_parser("status", help="show current campaign config and frontier")
    status.set_defaults(func=cmd_status)

    probe_run = subparsers.add_parser(
        "probe-run",
        help="run the probe model set without touching git state or the results log",
    )
    probe_run.add_argument("--scenario", default=None, help="override the scenario filter for an ad hoc run")
    probe_run.add_argument("--label", default=None)
    probe_run.add_argument("--dry-run", action="store_true")
    probe_run.set_defaults(func=cmd_probe_run)

    baseline = subparsers.add_parser("baseline", help="record the current clean HEAD as the campaign baseline")
    baseline.add_argument("--force", action="store_true")
    baseline.set_defaults(func=cmd_baseline)

    experiment = subparsers.add_parser(
        "experiment",
        help="commit the current scenario edit, run probes, and keep or discard automatically",
    )
    experiment.add_argument("--description", required=True)
    experiment.set_defaults(func=cmd_experiment)

    promote = subparsers.add_parser(
        "promote",
        help="run the broader promotion model set on the current clean HEAD",
    )
    promote.set_defaults(func=cmd_promote)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
