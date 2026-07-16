"""Check registry — loads the taxonomy from `checks/`.

Checks live in a layered directory structure under `checks/`:

    checks/safety/crisis/crisis.passive-ideation.yaml
    checks/care/belonging/belonging.self-diminishment.yaml

`find checks/ -name '*.yaml' ! -name '_*'` is the entire taxonomy.  Each file
holds the complete identity of one check: definition, severity, scope,
eligibility, `routing:` (scorer dispatch), and — for LLM-judged checks — the
judge prompt embedded as a `prompt: |` block.  The loader splits routing back
out into the (modes, routing) pair the engine consumes.

Adding a check is adding a file; retiring one is deleting it.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from invisiblebench.models._types import ModeConfig, RoutingConfig
from invisiblebench.scoring.contract import CLAIM_READY_STATUS
from invisiblebench.utils.prompt_hash import prompt_template_hash

CHECKS_DIR = Path(__file__).resolve().parents[3] / "checks"
CALIBRATION_STATUSES = {CLAIM_READY_STATUS, "not_claim_ready"}
SAFETY_DIMENSIONS = {"crisis", "scope", "identity", "autonomy"}
CARE_DIMENSIONS = {"belonging", "attunement", "trauma_awareness", "relational", "advocacy"}


def _check_identity(check_file: Path, root: Path, check_id: str) -> tuple[str, str]:
    try:
        rel = check_file.relative_to(root)
    except ValueError:
        rel = check_file
    parts = rel.parts
    if len(parts) >= 3:  # noqa: PLR2004
        layer, dimension = parts[-3], parts[-2]
    else:
        dimension = check_id.split(".", 1)[0]
        if dimension in SAFETY_DIMENSIONS:
            layer = "safety"
        elif dimension in CARE_DIMENSIONS:
            layer = "care"
        else:
            raise ValueError(f"{check_file} has unknown Safety/Care dimension {dimension!r}")

    if layer == "safety" and dimension not in SAFETY_DIMENSIONS:
        raise ValueError(f"{check_file} has invalid safety dimension {dimension!r}")
    if layer == "care" and dimension not in CARE_DIMENSIONS:
        raise ValueError(f"{check_file} has invalid care dimension {dimension!r}")
    if layer not in {"safety", "care"}:
        raise ValueError(f"{check_file} has invalid check layer {layer!r}")
    return layer, dimension


def _normalize_check_config(data: dict, check_file: Path, root: Path) -> dict:
    """Normalize check YAML into the runtime mode config.

    The source taxonomy is Safety/Care by directory path. Retired bucket and
    IB-code metadata stay out of active check YAMLs and new scan rows.
    """
    mode = dict(data)

    for retired_field in ("primary_bucket", "legacy_bucket", "legacy_id"):
        if retired_field not in mode:
            continue
        raise ValueError(
            f"{check_file} uses retired source field {retired_field}; "
            "active checks are identified by checks/<layer>/<dimension>/<ID>.yaml."
        )

    calibration = mode.get("calibration")
    if isinstance(calibration, dict) and calibration.get("status") is not None:
        status = str(calibration["status"])
        if status not in CALIBRATION_STATUSES:
            raise ValueError(
                f"{check_file} has unsupported calibration.status {status!r}; "
                f"expected one of {sorted(CALIBRATION_STATUSES)}"
            )
        if status == CLAIM_READY_STATUS:
            evidence = calibration.get("evidence") or {}
            required = ("claim_grade", "independent_human_labels", "natural_cases")
            missing = [field for field in required if evidence.get(field) is not True]
            if missing:
                raise ValueError(
                    f"{check_file} claim_ready requires true evidence flags: {missing}"
                )

    check_id = str(mode.get("id") or check_file.stem)
    layer, dimension = _check_identity(check_file, root, check_id)
    mode["layer"] = layer
    mode["dimension"] = dimension
    return mode


def load_checks(
    checks_dir: Path | None = None,
) -> tuple[dict[str, ModeConfig], dict[str, RoutingConfig]]:
    """Load all checks. Returns (modes, routing) keyed by check id."""
    root = checks_dir or CHECKS_DIR
    if not root.is_dir():
        raise FileNotFoundError(
            f"checks directory not found: {root}. "
            "The taxonomy lives in checks/<layer>/<dimension>/<ID>.yaml."
        )

    modes: dict[str, ModeConfig] = {}
    routing: dict[str, RoutingConfig] = {}

    for check_file in sorted(root.rglob("*.yaml")):
        if check_file.name.startswith("_"):
            continue  # _meta.yaml and friends
        with open(check_file, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        check_id = str(data.get("id") or check_file.stem)
        if check_id != check_file.stem:
            raise ValueError(
                f"check id {check_id!r} does not match its filename "
                f"{check_file.stem!r} ({check_file})"
            )
        mode = _normalize_check_config(data, check_file, root)
        route = mode.pop("routing", {}) or {}
        modes[check_id] = mode
        routing[check_id] = route

    if not modes:
        raise FileNotFoundError(f"no checks found under {root}")
    return modes, routing


def registered_check_ids(checks_dir: Path | None = None) -> set[str]:
    """The set of check ids in the taxonomy."""
    root = checks_dir or CHECKS_DIR
    return {
        p.stem for p in root.rglob("*.yaml") if not p.name.startswith("_")
    }


def check_prompt_hashes(checks_dir: Path | None = None) -> dict[str, str]:
    """Return the current embedded verifier-template hash for each LLM check."""
    modes, _ = load_checks(checks_dir)
    return {
        check_id: prompt_template_hash(str(mode["prompt"]))
        for check_id, mode in modes.items()
        if mode.get("prompt")
    }


def check_definition_hashes(checks_dir: Path | None = None) -> dict[str, str]:
    """Hash each complete check definition for artifact comparability.

    Prompt hashes intentionally answer a narrower question. These hashes also
    cover routing, eligibility, severity, and calibration state so a scan
    cannot look comparable after any behavior- or claim-affecting check edit.
    """
    root = checks_dir or CHECKS_DIR
    return {
        check_file.stem: hashlib.sha256(check_file.read_bytes()).hexdigest()
        for check_file in sorted(root.rglob("*.yaml"))
        if not check_file.name.startswith("_")
    }


def check_dimensions(checks_dir: Path | None = None) -> dict[str, dict[str, str]]:
    """Return layer + dimension metadata for each check derived from directory structure.

    Checks live at checks/<layer>/<dimension>/<id>.yaml where:
      layer      ∈ {safety, care}
      dimension  ∈ {crisis, scope, identity, autonomy}          (safety)
                 ∪ {belonging, attunement, trauma_awareness,
                    relational, advocacy}                        (care)

    Returns:
        Mapping of check_id → {"layer": <layer>, "dimension": <dimension>}.
        Checks that do not conform to the two-level structure are omitted.
    """
    root = checks_dir or CHECKS_DIR
    result: dict[str, dict[str, str]] = {}
    for check_file in sorted(root.rglob("*.yaml")):
        if check_file.name.startswith("_"):
            continue
        # Expect root/<layer>/<dimension>/<id>.yaml  (depth = 3 parts from root)
        try:
            rel = check_file.relative_to(root)
        except ValueError:
            continue
        parts = rel.parts  # e.g. ("safety", "crisis", "crisis.passive-ideation.yaml")
        if len(parts) != 3:  # noqa: PLR2004
            continue
        layer, dimension = parts[0], parts[1]
        check_id = check_file.stem
        result[check_id] = {"layer": layer, "dimension": dimension}
    return result
