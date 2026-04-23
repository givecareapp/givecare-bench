"""Calibration harness for per-mode gold sets.

Per `internal/taxonomy_v0.md` validation posture:
  40 examples per LLM-verifier mode —
    10 clear PASS / 10 clear FAIL / 10 ambiguous / 10 adversarial

Metrics computed per gold set:
  accuracy / precision / recall / FN rate / FP rate / UNCLEAR rate /
  inter-run stability / human-vs-verifier kappa

Validation tiers gated by these metrics before a mode is publishable.

Usage:
    from invisiblebench.evaluation.calibration import CalibrationHarness
    harness = CalibrationHarness()
    results = harness.run_mode_calibration(mode_id="IB-A1", verifier=llm_verifier)
"""

from __future__ import annotations

import json
import logging
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from invisiblebench.evaluation.verifiers.base import (
    FAILURE_VERDICTS,
    PASS_VERDICTS,
    Verdict,
    Verifier,
)

logger = logging.getLogger(__name__)


REPO_ROOT = Path(__file__).resolve().parents[3]
GOLD_SETS_DIR = REPO_ROOT / "internal" / "calibration" / "gold_sets"


@dataclass
class GoldExample:
    """One calibration example — transcript + scenario + expected verdict."""

    example_id: str
    mode_id: str
    bucket: str  # "clear_pass" | "clear_fail" | "ambiguous" | "adversarial"
    expected: Verdict
    transcript: list[dict[str, Any]]
    scenario: dict[str, Any]
    author: Optional[str] = None
    adjudication_notes: Optional[str] = None


@dataclass
class CalibrationMetrics:
    """Per-mode calibration metrics. These gate publishability."""

    mode_id: str
    n_examples: int
    accuracy: float
    precision: Optional[float]
    recall: Optional[float]
    false_negative_rate: Optional[float]
    false_positive_rate: Optional[float]
    unclear_rate: float
    inter_run_stability: Optional[float]  # K>1 repetitions agreement
    human_verifier_kappa: Optional[float]
    per_bucket_accuracy: dict[str, float] = field(default_factory=dict)
    confusion_matrix: dict[str, dict[str, int]] = field(default_factory=dict)

    def tier(self) -> str:
        """Classify mode by Tier 1/2/3/4 per taxonomy_v0."""
        if self.accuracy < 0.6 or self.n_examples < 20:
            return "Tier_4_exploratory"
        if self.recall is not None and self.recall < 0.80:
            return "Tier_3_beta"
        if self.accuracy >= 0.80 and (self.recall or 1.0) >= 0.85:
            return "Tier_1_validation_grade"
        return "Tier_2_calibrated_secondary"

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode_id": self.mode_id,
            "n_examples": self.n_examples,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "false_negative_rate": self.false_negative_rate,
            "false_positive_rate": self.false_positive_rate,
            "unclear_rate": self.unclear_rate,
            "inter_run_stability": self.inter_run_stability,
            "human_verifier_kappa": self.human_verifier_kappa,
            "per_bucket_accuracy": dict(self.per_bucket_accuracy),
            "confusion_matrix": dict(self.confusion_matrix),
            "validation_tier": self.tier(),
        }


class CalibrationHarness:
    """Run a verifier against a per-mode gold set and compute metrics."""

    def __init__(self, gold_sets_dir: Optional[Path] = None) -> None:
        self.gold_sets_dir = gold_sets_dir or GOLD_SETS_DIR

    def load_gold_set(self, mode_id: str) -> list[GoldExample]:
        """Gold sets live at internal/calibration/gold_sets/<MODE_ID>.jsonl."""
        path = self.gold_sets_dir / f"{mode_id}.jsonl"
        if not path.exists():
            logger.warning("No gold set for %s at %s", mode_id, path)
            return []
        examples: list[GoldExample] = []
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                examples.append(
                    GoldExample(
                        example_id=data.get("example_id", f"{mode_id}_{i:03d}"),
                        mode_id=mode_id,
                        bucket=data["bucket"],
                        expected=Verdict(data["expected"]),
                        transcript=data["transcript"],
                        scenario=data.get("scenario", {}),
                        author=data.get("author"),
                        adjudication_notes=data.get("adjudication_notes"),
                    )
                )
        return examples

    def run_mode_calibration(
        self,
        mode_id: str,
        verifier: Verifier,
        mode_config: dict[str, Any],
        routing_config: dict[str, Any],
        repetitions_per_example: int = 3,
    ) -> CalibrationMetrics:
        """Run the verifier against every gold example for this mode."""
        gold = self.load_gold_set(mode_id)
        if not gold:
            return CalibrationMetrics(
                mode_id=mode_id,
                n_examples=0,
                accuracy=0.0,
                precision=None,
                recall=None,
                false_negative_rate=None,
                false_positive_rate=None,
                unclear_rate=0.0,
                inter_run_stability=None,
                human_verifier_kappa=None,
            )

        per_example_verdicts: list[tuple[Verdict, Verdict, str]] = []
        stability_per_example: list[float] = []

        for ex in gold:
            # Run K times per example for stability
            runs: list[Verdict] = []
            for _ in range(repetitions_per_example):
                try:
                    result = verifier.verify(
                        transcript=ex.transcript,
                        scenario=ex.scenario,
                        mode_config=mode_config,
                        routing_config=routing_config,
                    )
                    runs.append(result.verdict)
                except Exception as e:
                    logger.warning("Verifier error on %s: %s", ex.example_id, e)
                    runs.append(Verdict.UNCLEAR)

            # Majority vote; ties → UNCLEAR
            from collections import Counter
            top = Counter(runs).most_common(1)
            if top and top[0][1] > repetitions_per_example / 2:
                verdict = top[0][0]
            else:
                verdict = Verdict.UNCLEAR

            # Intra-example stability: fraction of runs matching the majority
            stability_per_example.append(top[0][1] / repetitions_per_example if top else 0.0)

            per_example_verdicts.append((ex.expected, verdict, ex.bucket))

        return self._compute_metrics(
            mode_id,
            per_example_verdicts,
            stability_per_example,
        )

    def _compute_metrics(
        self,
        mode_id: str,
        verdicts: list[tuple[Verdict, Verdict, str]],
        stability: list[float],
    ) -> CalibrationMetrics:
        n = len(verdicts)
        if n == 0:
            return CalibrationMetrics(
                mode_id=mode_id,
                n_examples=0,
                accuracy=0.0,
                precision=None,
                recall=None,
                false_negative_rate=None,
                false_positive_rate=None,
                unclear_rate=0.0,
                inter_run_stability=None,
                human_verifier_kappa=None,
            )

        tp = fp = tn = fn = unclear = 0
        per_bucket: dict[str, list[bool]] = {}
        confusion: dict[str, dict[str, int]] = {}

        for expected, actual, bucket in verdicts:
            correct = expected == actual
            per_bucket.setdefault(bucket, []).append(correct)
            confusion.setdefault(expected.value, {}).setdefault(actual.value, 0)
            confusion[expected.value][actual.value] += 1

            if actual == Verdict.UNCLEAR:
                unclear += 1
                continue

            exp_is_fail = expected in FAILURE_VERDICTS
            act_is_fail = actual in FAILURE_VERDICTS

            if exp_is_fail and act_is_fail:
                tp += 1
            elif exp_is_fail and not act_is_fail:
                fn += 1
            elif not exp_is_fail and act_is_fail:
                fp += 1
            else:
                tn += 1

        accuracy = sum(1 for e, a, _ in verdicts if e == a) / n

        precision = tp / (tp + fp) if (tp + fp) > 0 else None
        recall = tp / (tp + fn) if (tp + fn) > 0 else None
        false_negative_rate = fn / (tp + fn) if (tp + fn) > 0 else None
        false_positive_rate = fp / (fp + tn) if (fp + tn) > 0 else None
        unclear_rate = unclear / n

        per_bucket_accuracy = {
            bucket: sum(results) / len(results)
            for bucket, results in per_bucket.items()
        }

        stability_mean = statistics.mean(stability) if stability else None

        # Cohen's κ simplified: p_o - p_e / (1 - p_e)
        kappa = self._cohens_kappa(verdicts)

        return CalibrationMetrics(
            mode_id=mode_id,
            n_examples=n,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            false_negative_rate=false_negative_rate,
            false_positive_rate=false_positive_rate,
            unclear_rate=unclear_rate,
            inter_run_stability=stability_mean,
            human_verifier_kappa=kappa,
            per_bucket_accuracy=per_bucket_accuracy,
            confusion_matrix=confusion,
        )

    def _cohens_kappa(
        self, verdicts: list[tuple[Verdict, Verdict, str]]
    ) -> Optional[float]:
        """Cohen's kappa between expected (human gold) and actual (verifier)."""
        n = len(verdicts)
        if n == 0:
            return None

        # Binary collapse: pass vs. fail (ignoring UNCLEAR for κ calc)
        binary_pairs = [
            (e in PASS_VERDICTS, a in PASS_VERDICTS)
            for e, a, _ in verdicts
            if a != Verdict.UNCLEAR and e != Verdict.UNCLEAR
        ]
        if not binary_pairs:
            return None

        po = sum(1 for e, a in binary_pairs if e == a) / len(binary_pairs)
        exp_pos = sum(1 for e, _ in binary_pairs if e) / len(binary_pairs)
        act_pos = sum(1 for _, a in binary_pairs if a) / len(binary_pairs)
        pe = exp_pos * act_pos + (1 - exp_pos) * (1 - act_pos)
        if pe == 1.0:
            return 1.0
        return (po - pe) / (1 - pe)
