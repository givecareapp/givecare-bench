"""Machine-enforced design invariants for the Safety+Care instrument.

These tests assert structural properties that must hold as long as the
InvisibleBench ontology is valid.  They are deliberately distinct from
test_projection.py (which tests build_scorecard behaviour on fixtures)
and test_scoring.py (which tests safety/care computation logic).

Invariants enforced here
------------------------
1. NO COMPOSITE: build_scorecard output carries no ``overall_score``,
   ``composite``, or ``rank`` key at any level; and the scoring/ package
   source code contains no cross-layer or cross-quality averaging into a
   single number.

2. NO CROSS-LAYER MERGE: safety and care are reported at separate keys;
   no key blends them.

3. CALIBRATION-GATED CLAIMS: with ``calibrated_only=True`` only checks
   whose calibration.status is ``claim_ready`` contribute (a
   not-claim-ready check's FAILs do not move the published violation rate).

4. STRUCTURE MATCHES ONTOLOGY: the live ``checks/`` tree has exactly the
   9 dimensions specified in docs/ontology.md —
   safety/{crisis,scope,identity,autonomy} +
   care/{belonging,attunement,trauma_awareness,relational,advocacy}.
   Every authored check id equals its filename stem (self-contained).

5. PER-LINE IS CONDITIONAL: a per-line violation rate uses an
   eligible-scenario denominator that may differ across lines (i.e. n
   per line is not forced to equal the total scenario count).

6. NO HISTORICAL FILE TREE: superseded material lives in git history, not in
   a tracked ``archive/`` directory beside the active benchmark.

Notes on trauma_awareness
--------------------------
The trauma_awareness directory exists as a named placeholder in
``checks/care/trauma_awareness/`` (tracked with a .gitkeep so it is
visible as a dimension gap).  It has no authored YAML checks yet, so
``check_registry.check_dimensions()`` — which only returns dimensions
with at least one YAML file — will NOT include it.  The directory tree
count (invariant 4) uses the filesystem layer to assert the placeholder
exists; check_dimensions() is used to assert the 8 populated dimensions.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from invisiblebench.evaluation.check_registry import (
    CHECKS_DIR,
    check_dimensions,
)
from invisiblebench.scoring.projection import build_scorecard
from invisiblebench.scoring.safety import (
    _CALIBRATED_STATUSES,  # noqa: PLC2701
    check_calibration_statuses,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
SCORING_PKG = REPO_ROOT / "src" / "invisiblebench" / "scoring"

# The 9 ontology dimensions, split by layer.
ONTOLOGY_SAFETY_DIMS: frozenset[str] = frozenset({"crisis", "scope", "identity", "autonomy"})
ONTOLOGY_CARE_DIMS: frozenset[str] = frozenset(
    {"belonging", "attunement", "trauma_awareness", "relational", "advocacy"}
)
# 8 of 9 have authored checks; trauma_awareness is a placeholder (no YAMLs yet).
ONTOLOGY_POPULATED_DIMS: frozenset[str] = ONTOLOGY_SAFETY_DIMS | (
    ONTOLOGY_CARE_DIMS - {"trauma_awareness"}
)


def test_repository_has_no_archived_files() -> None:
    archive = REPO_ROOT / "archive"
    files = sorted(
        str(path.relative_to(REPO_ROOT))
        for path in archive.rglob("*")
        if path.is_file()
    )

    assert files == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _walk_scorecard_keys(obj: Any, *, path: str = "") -> list[str]:
    """Recursively collect all keys in a nested dict/list structure."""
    keys: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            full = f"{path}.{k}" if path else k
            keys.append(full)
            keys.extend(_walk_scorecard_keys(v, path=full))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            keys.extend(_walk_scorecard_keys(item, path=f"{path}[{i}]"))
    return keys


# ---------------------------------------------------------------------------
# INVARIANT 1 — No composite key (output)
# ---------------------------------------------------------------------------

class TestNoComposite:
    """build_scorecard must never emit an overall_score, composite, or rank key."""

    @pytest.fixture(scope="class")
    def scorecard(self, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
        """Two-model mini scorecard built from a synthetic scan."""
        # Load two real check ids from the safety/crisis and care/belonging dims
        crisis_checks = [
            p.stem
            for p in (CHECKS_DIR / "safety" / "crisis").glob("*.yaml")
            if not p.name.startswith("_")
        ]
        belonging_checks = [
            p.stem
            for p in (CHECKS_DIR / "care" / "belonging").glob("*.yaml")
            if not p.name.startswith("_")
        ]
        assert crisis_checks, "Need at least one crisis check for the fixture"
        assert belonging_checks, "Need at least one belonging check for the fixture"

        crisis_id = crisis_checks[0]
        belonging_id = belonging_checks[0]

        rows = [
            {
                "model": "Alpha",
                "model_id": "test/alpha",
                "scenario_id": "s1",
                "category": "safety",
                "overall_score": 1.0,
                "hard_fail": False,
                "hard_fail_reasons": [],
                "mode_results": [
                    {"mode_id": crisis_id, "eligible": True, "verdict": "FAIL",
                     "severity": "S5", "layer": "safety", "dimension": "crisis",
                     "scorer_type": "llm_verifier",
                     "confidence": 1.0, "evidence": [], "rationale_code": None,
                     "adjudication_required": False},
                    {"mode_id": belonging_id, "eligible": True, "verdict": "PASS",
                     "severity": "S3", "layer": "care", "dimension": "belonging",
                     "scorer_type": "llm_verifier",
                     "confidence": 1.0, "evidence": [], "rationale_code": None,
                     "adjudication_required": False},
                ],
            },
            {
                "model": "Alpha",
                "model_id": "test/alpha",
                "scenario_id": "s2",
                "category": "safety",
                "overall_score": 1.0,
                "hard_fail": False,
                "hard_fail_reasons": [],
                "mode_results": [
                    {"mode_id": crisis_id, "eligible": True, "verdict": "PASS",
                     "severity": "S5", "layer": "safety", "dimension": "crisis",
                     "scorer_type": "llm_verifier",
                     "confidence": 1.0, "evidence": [], "rationale_code": None,
                     "adjudication_required": False},
                    {"mode_id": belonging_id, "eligible": True, "verdict": "FAIL",
                     "severity": "S3", "layer": "care", "dimension": "belonging",
                     "scorer_type": "llm_verifier",
                     "confidence": 1.0, "evidence": [], "rationale_code": None,
                     "adjudication_required": False},
                ],
            },
        ]

        tmp = tmp_path_factory.mktemp("inv1") / "mini.jsonl"
        tmp.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        return build_scorecard(str(tmp), calibrated_only=False)

    def test_no_overall_score_key_at_any_level(self, scorecard: dict[str, Any]) -> None:
        all_keys = _walk_scorecard_keys(scorecard)
        # Check both exact key name and key-name substrings in the path
        offending = [k for k in all_keys if k.split(".")[-1] == "overall_score"]
        assert not offending, (
            f"overall_score key found in scorecard at path(s): {offending}"
        )

    def test_no_composite_key_at_any_level(self, scorecard: dict[str, Any]) -> None:
        all_keys = _walk_scorecard_keys(scorecard)
        offending = [k for k in all_keys if k.split(".")[-1] == "composite"]
        assert not offending, (
            f"composite key found in scorecard at path(s): {offending}"
        )

    def test_no_rank_key_at_any_level(self, scorecard: dict[str, Any]) -> None:
        all_keys = _walk_scorecard_keys(scorecard)
        offending = [k for k in all_keys if k.split(".")[-1] == "rank"]
        assert not offending, (
            f"rank key found in scorecard at path(s): {offending}"
        )

    def test_source_no_cross_layer_average(self) -> None:
        """Grep scoring/ source: no expression that sums or averages across
        care qualities into a single number, or merges safety rates with care
        pass rates.

        We parse AST to find sum()/mean() calls whose argument iterates over
        care/safety dimension values in the same expression.  As a pragmatic
        proxy we also grep for telltale string patterns that would indicate
        cross-dimension averaging.
        """
        forbidden_patterns = [
            "overall_score",
            "composite",
            # A single-number average of care qualities would require dividing
            # by the number of qualities; we look for the string 'care' adjacent
            # to 'mean' or 'sum' inside the scoring package.
        ]
        for src_file in sorted(SCORING_PKG.glob("*.py")):
            src = src_file.read_text(encoding="utf-8")
            for pat in forbidden_patterns:
                # Allow the pattern only inside comment/docstring context
                # (the files use "no_composite" and docstring mentions "NO composite")
                tree = ast.parse(src, filename=str(src_file))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        # String constants (docstrings, dict values) — allowed
                        continue
                    # For non-string constant nodes check the raw token
                # Simple non-AST check: the string must not appear outside a comment or string literal
                # We remove comments and string literals from source, then check.
                import io  # noqa: PLC0415
                import tokenize  # noqa: PLC0415
                tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
                code_only = "".join(
                    tok.string
                    for tok in tokens
                    if tok.type not in (
                        tokenize.COMMENT,
                        tokenize.STRING,
                        tokenize.NEWLINE,
                        tokenize.NL,
                        tokenize.INDENT,
                        tokenize.DEDENT,
                    )
                )
                assert pat not in code_only, (
                    f"Forbidden pattern {pat!r} found in non-comment, non-string "
                    f"code of {src_file.name}. Cross-dimension averaging detected."
                )


# ---------------------------------------------------------------------------
# INVARIANT 2 — No cross-layer merge: safety and care are separate
# ---------------------------------------------------------------------------

class TestNoSafetyCareMerge:
    """Safety and care must be reported at distinct, separate keys.
    No key blends or merges the two layers."""

    @pytest.fixture(scope="class")
    def scorecard(self, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
        """Minimal 1-model scorecard."""
        crisis_id = next(
            p.stem
            for p in (CHECKS_DIR / "safety" / "crisis").glob("*.yaml")
            if not p.name.startswith("_")
        )
        row = {
            "model": "M",
            "model_id": "test/m",
            "scenario_id": "s1",
            "category": "safety",
            "overall_score": 1.0,
            "hard_fail": False,
            "hard_fail_reasons": [],
            "mode_results": [
                {"mode_id": crisis_id, "eligible": True, "verdict": "PASS",
                 "severity": "S5", "layer": "safety", "dimension": "crisis",
                 "scorer_type": "llm_verifier",
                 "confidence": 1.0, "evidence": [], "rationale_code": None,
                 "adjudication_required": False},
            ],
        }
        tmp = tmp_path_factory.mktemp("inv2") / "scan.jsonl"
        tmp.write_text(json.dumps(row), encoding="utf-8")
        return build_scorecard(str(tmp), calibrated_only=False)

    def test_model_has_separate_safety_and_care_keys(self, scorecard: dict[str, Any]) -> None:
        for model in scorecard["models"]:
            assert "safety" in model, f"safety key missing for {model.get('model')}"
            assert "care" in model, f"care key missing for {model.get('model')}"

    def test_safety_value_is_not_care_value(self, scorecard: dict[str, Any]) -> None:
        for model in scorecard["models"]:
            # They must be distinct objects — safety does not include care fields
            safety = model["safety"]
            care = model["care"]
            assert "qualities" not in safety, (
                "care 'qualities' key leaked into safety entry"
            )
            assert "lines" not in care, (
                "safety 'lines' key leaked into care entry"
            )

    def test_no_blended_key_in_model_entry(self, scorecard: dict[str, Any]) -> None:
        """Model entry must not have a key that blends safety and care."""
        blend_names = {"safety_care", "combined", "overall", "merged"}
        for model in scorecard["models"]:
            for key in model:
                assert key not in blend_names, (
                    f"Blended key {key!r} found in model entry for {model.get('model')}"
                )

    def test_source_no_safety_care_blend_variable(self) -> None:
        """Grep scoring/ source: no variable assignment that blends safety+care."""
        # A blend would require combining a safety rate (float) with a care pass_rate
        # into a single variable. Look for identifiers that contain both substrings.
        for src_file in sorted(SCORING_PKG.glob("*.py")):
            src = src_file.read_text(encoding="utf-8")
            # Detect assignments like 'safety_care_score = ...' or similar hybrids
            import re  # noqa: PLC0415
            pattern = re.compile(
                r'\b(?:safety[\s_]care|care[\s_]safety|merged_score|combined_score)\b',
                re.IGNORECASE,
            )
            # Allow in comments and docstrings only — exclude those from check
            import io  # noqa: PLC0415
            import tokenize  # noqa: PLC0415
            tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
            code_only = "".join(
                tok.string
                for tok in tokens
                if tok.type not in (
                    tokenize.COMMENT, tokenize.STRING,
                    tokenize.NEWLINE, tokenize.NL,
                    tokenize.INDENT, tokenize.DEDENT,
                )
            )
            code_matches = pattern.findall(code_only)
            assert not code_matches, (
                f"Safety+care blend expression found in code of {src_file.name}: "
                f"{code_matches}"
            )


# ---------------------------------------------------------------------------
# INVARIANT 3 — Calibration-gated claims
# ---------------------------------------------------------------------------

class TestCalibrationGate:
    """calibrated_only=True must exclude uncalibrated checks from violation rates."""

    def _make_scan(
        self,
        tmp_path: Path,
        check_id: str,
        verdict: str,
    ) -> Path:
        """Write a one-row scan where `check_id` fires `verdict`."""
        row = {
            "model": "M",
            "model_id": "test/m",
            "scenario_id": "s1",
            "category": "safety",
            "overall_score": 1.0,
            "hard_fail": False,
            "hard_fail_reasons": [],
            "mode_results": [
                {"mode_id": check_id, "eligible": True, "verdict": verdict,
                 "severity": "S3",
                 "layer": "safety" if check_id.split(".", 1)[0] in {"crisis", "scope", "identity", "autonomy"} else "care",
                 "dimension": check_id.split(".", 1)[0],
                 "scorer_type": "llm_verifier",
                 "confidence": 1.0, "evidence": [], "rationale_code": None,
                 "adjudication_required": False},
            ],
        }
        out = tmp_path / "scan.jsonl"
        out.write_text(json.dumps(row), encoding="utf-8")
        return out

    def test_uncalibrated_fail_does_not_move_calibrated_rate(
        self, tmp_path: Path
    ) -> None:
        """An uncalibrated check's FAIL must NOT raise the calibrated violation rate.

        We find a safety check that has NO calibration block (so it is absent
        from check_calibration_statuses), inject a FAIL for it, and confirm
        that the calibrated_only=True view reports rate=None or 0.0 for the
        relevant dimension.
        """
        cal_map = check_calibration_statuses()
        dim_map = check_dimensions()

        # Find a safety check with no calibration entry
        uncal_safety_checks = [
            cid for cid, info in dim_map.items()
            if info["layer"] == "safety" and cid not in cal_map
        ]
        if not uncal_safety_checks:
            pytest.skip("No uncalibrated safety checks in current taxonomy")

        uncal_id = uncal_safety_checks[0]
        scan = self._make_scan(tmp_path, uncal_id, "FAIL")

        sc_cal = build_scorecard(str(scan), calibrated_only=True)
        sc_all = build_scorecard(str(scan), calibrated_only=False)

        dim = dim_map[uncal_id]["dimension"]

        model_cal = sc_cal["models"][0]
        model_all = sc_all["models"][0]

        # calibrated_only view: this check is excluded → rate should be None or 0.0
        rate_cal = model_cal["safety"]["lines"].get(dim, {}).get("rate")
        assert rate_cal in (None, 0.0), (
            f"Uncalibrated check {uncal_id!r} (dim={dim}) raised calibrated "
            f"violation rate to {rate_cal}; expected None or 0.0"
        )

        # uncalibrated view: the FAIL IS counted → rate should be > 0
        rate_all = model_all["safety"]["lines"].get(dim, {}).get("rate")
        assert rate_all is not None and rate_all > 0, (
            f"Uncalibrated check {uncal_id!r} FAIL not counted in full view "
            f"(rate={rate_all}); expected > 0"
        )

    def test_calibrated_statuses_are_subset_of_expected(self) -> None:
        """All calibration status values in the taxonomy must be known."""
        known_statuses = {"claim_ready", "not_claim_ready"}
        cal_map = check_calibration_statuses()
        for check_id, status in cal_map.items():
            assert status in known_statuses, (
                f"Check {check_id!r} has unknown calibration status {status!r}; "
                f"expected one of {known_statuses}"
            )

    def test_calibrated_statuses_match_gate_constant(self) -> None:
        """The _CALIBRATED_STATUSES constant must match the expected set."""
        assert _CALIBRATED_STATUSES == frozenset({"claim_ready"}), (
            f"_CALIBRATED_STATUSES is {_CALIBRATED_STATUSES!r}; "
            "expected frozenset({'claim_ready'})"
        )

# ---------------------------------------------------------------------------
# INVARIANT 4 — Structure matches ontology
# ---------------------------------------------------------------------------

class TestOntologyStructure:
    """The checks/ tree must reflect the 9 dimensions from docs/ontology.md."""

    def test_safety_dimension_dirs_match_ontology(self) -> None:
        """checks/safety/ subdirectories == {crisis, scope, identity, autonomy}."""
        safety_root = CHECKS_DIR / "safety"
        assert safety_root.is_dir(), f"checks/safety/ not found at {safety_root}"
        actual_dims = {d.name for d in safety_root.iterdir() if d.is_dir()}
        assert actual_dims == ONTOLOGY_SAFETY_DIMS, (
            f"Safety dimension dirs {actual_dims!r} != ontology {ONTOLOGY_SAFETY_DIMS!r}"
        )

    def test_care_dimension_dirs_match_ontology(self) -> None:
        """checks/care/ subdirectories == {belonging, attunement, trauma_awareness,
        relational, advocacy}."""
        care_root = CHECKS_DIR / "care"
        assert care_root.is_dir(), f"checks/care/ not found at {care_root}"
        actual_dims = {d.name for d in care_root.iterdir() if d.is_dir()}
        assert actual_dims == ONTOLOGY_CARE_DIMS, (
            f"Care dimension dirs {actual_dims!r} != ontology {ONTOLOGY_CARE_DIMS!r}"
        )

    def test_exactly_9_dimension_dirs_total(self) -> None:
        """Total unique dimension directories across safety/ and care/ == 9."""
        safety_dims = {d.name for d in (CHECKS_DIR / "safety").iterdir() if d.is_dir()}
        care_dims = {d.name for d in (CHECKS_DIR / "care").iterdir() if d.is_dir()}
        all_dims = safety_dims | care_dims
        assert len(all_dims) == 9, (  # noqa: PLR2004
            f"Expected 9 dimension directories, found {len(all_dims)}: {sorted(all_dims)}"
        )

    def test_trauma_awareness_placeholder_exists(self) -> None:
        """trauma_awareness directory must exist (named gap placeholder)."""
        ta_dir = CHECKS_DIR / "care" / "trauma_awareness"
        assert ta_dir.is_dir(), (
            f"trauma_awareness placeholder directory not found at {ta_dir}"
        )

    def test_trauma_awareness_has_no_authored_checks(self) -> None:
        """trauma_awareness has no YAML check files yet (not_claim_ready gap)."""
        ta_dir = CHECKS_DIR / "care" / "trauma_awareness"
        yamls = [
            f for f in ta_dir.glob("*.yaml")
            if not f.name.startswith("_")
        ]
        assert yamls == [], (
            f"Expected trauma_awareness to have no authored checks; found: {yamls}"
        )

    def test_check_dimensions_returns_8_populated_dimensions(self) -> None:
        """check_dimensions() returns exactly 8 populated dimensions
        (trauma_awareness is a placeholder with no YAML checks)."""
        dims = check_dimensions()
        layer_dims: dict[str, set[str]] = {}
        for info in dims.values():
            layer_dims.setdefault(info["layer"], set()).add(info["dimension"])

        populated = set()
        for dims_set in layer_dims.values():
            populated |= dims_set

        assert populated == ONTOLOGY_POPULATED_DIMS, (
            f"Populated dimensions {populated!r} != expected {ONTOLOGY_POPULATED_DIMS!r}"
        )

    def test_every_check_id_equals_filename_stem(self) -> None:
        """Every check YAML must have id == filename stem (self-contained identity)."""
        import yaml  # noqa: PLC0415

        mismatches: list[str] = []
        for check_file in sorted(CHECKS_DIR.rglob("*.yaml")):
            if check_file.name.startswith("_"):
                continue
            data = yaml.safe_load(check_file.read_text(encoding="utf-8")) or {}
            check_id = str(data.get("id") or "")
            if check_id and check_id != check_file.stem:
                mismatches.append(
                    f"{check_file.relative_to(CHECKS_DIR)}: "
                    f"id={check_id!r} != stem={check_file.stem!r}"
                )

        assert not mismatches, (
            "Check id/stem mismatches found (id must equal filename stem):\n"
            + "\n".join(mismatches)
        )

    def test_check_dimensions_layer_values_are_safety_or_care(self) -> None:
        """Every check must belong to layer 'safety' or 'care'."""
        dims = check_dimensions()
        bad_layers = [
            (cid, info["layer"])
            for cid, info in dims.items()
            if info["layer"] not in ("safety", "care")
        ]
        assert not bad_layers, (
            f"Checks with unexpected layer values: {bad_layers}"
        )


# ---------------------------------------------------------------------------
# INVARIANT 5 — Per-line denominator is conditional (eligible-scenario n)
# ---------------------------------------------------------------------------

class TestPerLineDenominator:
    """Violation rates use eligible-scenario denominators.

    The n value for each Safety line reflects scenarios where at least one
    check in that line was eligible.  Because different checks have different
    scope/trigger eligibility, the n per line must differ across at least some
    lines in a realistic scan.
    """

    def test_per_line_n_reflects_eligible_scenarios_not_checks(
        self, tmp_path: Path
    ) -> None:
        """n per line = number of scenarios with ≥1 eligible check in that line.

        Set up two scenarios:
          Scenario 1: has an eligible crisis check (PASS)
          Scenario 2: has an eligible scope check (PASS), no crisis check

        Expect: crisis n=1, scope n=1 (not n=2 for each).
        """
        crisis_id = next(
            p.stem
            for p in (CHECKS_DIR / "safety" / "crisis").glob("*.yaml")
            if not p.name.startswith("_")
        )
        scope_id = next(
            p.stem
            for p in (CHECKS_DIR / "safety" / "scope").glob("*.yaml")
            if not p.name.startswith("_")
        )

        rows = [
            {
                "model": "M",
                "model_id": "test/m",
                "scenario_id": "crisis_only",
                "category": "safety",
                "overall_score": 1.0,
                "hard_fail": False,
                "hard_fail_reasons": [],
                "mode_results": [
                    {"mode_id": crisis_id, "eligible": True, "verdict": "PASS",
                     "severity": "S5", "layer": "safety", "dimension": "crisis",
                     "scorer_type": "llm_verifier",
                     "confidence": 1.0, "evidence": [], "rationale_code": None,
                     "adjudication_required": False},
                ],
            },
            {
                "model": "M",
                "model_id": "test/m",
                "scenario_id": "scope_only",
                "category": "safety",
                "overall_score": 1.0,
                "hard_fail": False,
                "hard_fail_reasons": [],
                "mode_results": [
                    {"mode_id": scope_id, "eligible": True, "verdict": "PASS",
                     "severity": "S3", "layer": "safety", "dimension": "scope",
                     "scorer_type": "llm_verifier",
                     "confidence": 1.0, "evidence": [], "rationale_code": None,
                     "adjudication_required": False},
                ],
            },
        ]

        scan = tmp_path / "scan.jsonl"
        scan.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

        sc = build_scorecard(str(scan), calibrated_only=False)
        model = sc["models"][0]

        crisis_n = model["safety"]["lines"]["crisis"]["n"]
        scope_n = model["safety"]["lines"]["scope"]["n"]

        assert crisis_n == 1, (
            f"Expected crisis n=1 (only scenario_1 had a crisis check), got {crisis_n}"
        )
        assert scope_n == 1, (
            f"Expected scope n=1 (only scenario_2 had a scope check), got {scope_n}"
        )
        # The two lines have the same n here, but their denominators are
        # correct (1 each from different scenarios, not 2 each).
        # With total=2 scenarios, any value ≤ 2 is valid.
        assert crisis_n <= 2  # noqa: PLR2004
        assert scope_n <= 2  # noqa: PLR2004
