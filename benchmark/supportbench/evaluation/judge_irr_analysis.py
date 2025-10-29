"""
Inter-Rater Reliability (IRR) analysis for tri-judge ensemble.

Tests whether the 3 judges (Claude Sonnet, Gemini Pro, Claude Opus)
agree on their dimension scores.

Key metrics:
- Spearman ρ: Rank correlation between judge pairs
- Threshold: ρ > 0.7 required for reliability claims
- Cohen's κ: Agreement on autofail decisions (binary)

Usage:
    python -m supportbench.evaluation.judge_irr_analysis \
        --results data/results/benchmark_run.json \
        --output data/results/irr_analysis.json
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from scipy.stats import spearmanr

logger = logging.getLogger(__name__)


class JudgeIRRAnalyzer:
    """Analyze inter-rater reliability for tri-judge ensemble."""

    def __init__(self):
        """Initialize analyzer."""
        self.judge_names = ["judge_1", "judge_2", "judge_3"]  # TODO: verify from actual results
        self.dimension_names = [
            "memory",
            "trauma",
            "belonging",
            "compliance",
            "safety",
            "relational_quality",
            "actionable_support",
            "longitudinal_consistency"
        ]

    def analyze(self, results_path: Path) -> Dict:
        """
        Calculate inter-rater reliability between judges.

        Args:
            results_path: Path to JSON file with benchmark results

        Returns:
            Dict with IRR metrics including Spearman ρ for each dimension
        """
        # TODO: Implement after first benchmark run
        # 1. Load results from JSON
        # 2. Extract judge scores per turn per dimension
        # 3. Calculate pairwise Spearman ρ for each dimension
        # 4. Calculate Cohen's κ for autofail agreements
        # 5. Generate judge agreement heatmap
        # 6. Return analysis results

        raise NotImplementedError(
            "IRR analysis requires benchmark results. Run this after:\n"
            "  python -m supportbench.yaml_cli --scenario <scenario> --transcript <transcript> --rules <rules>\n"
            "Then call: python -m supportbench.evaluation.judge_irr_analysis --results <results.json>"
        )

    def _extract_judge_scores(self, results: Dict) -> Dict[str, Dict[str, List[float]]]:
        """
        Extract judge scores organized by dimension.

        Args:
            results: Loaded benchmark results JSON

        Returns:
            Dict[dimension][judge_name] = list of scores across all turns
        """
        # TODO: Implement based on actual results structure
        pass

    def _calculate_pairwise_correlation(
        self,
        judge1_scores: List[float],
        judge2_scores: List[float]
    ) -> Tuple[float, float]:
        """
        Calculate Spearman ρ between two judges.

        Args:
            judge1_scores: Scores from first judge
            judge2_scores: Scores from second judge

        Returns:
            Tuple of (correlation, p_value)
        """
        return spearmanr(judge1_scores, judge2_scores)

    def _calculate_cohens_kappa(
        self,
        judge1_autofails: List[bool],
        judge2_autofails: List[bool]
    ) -> float:
        """
        Calculate Cohen's κ for autofail agreement.

        Args:
            judge1_autofails: Binary autofail decisions from judge 1
            judge2_autofails: Binary autofail decisions from judge 2

        Returns:
            Cohen's κ value
        """
        # TODO: Implement Cohen's kappa calculation
        pass

    def _generate_heatmap(self, correlations: Dict[str, float], output_path: Path):
        """
        Generate heatmap of judge correlations across dimensions.

        Args:
            correlations: Dict of dimension -> correlation value
            output_path: Where to save the heatmap
        """
        # TODO: Implement using matplotlib/seaborn
        pass

    def _interpret_results(self, correlations: Dict[str, Dict[str, float]]) -> str:
        """
        Interpret IRR results and provide recommendations.

        Args:
            correlations: Dict[dimension][judge_pair] = correlation

        Returns:
            Interpretation string
        """
        # Calculate mean correlation across all dimension-judge pairs
        all_corrs = []
        for dim_corrs in correlations.values():
            all_corrs.extend(dim_corrs.values())

        mean_corr = np.mean(all_corrs)
        min_corr = np.min(all_corrs)

        if min_corr < 0.5:
            return (
                f"⚠️  CRITICAL: Minimum correlation {min_corr:.2f} (< 0.5).\n"
                "Judges show poor agreement on some dimensions.\n"
                "RECOMMENDATION: Review judge prompts, consider removing unreliable judge."
            )
        elif mean_corr < 0.7:
            return (
                f"⚠️  WARNING: Mean correlation {mean_corr:.2f} (< 0.7).\n"
                "Judge agreement is below reliability threshold.\n"
                "RECOMMENDATION: Report IRR scores and acknowledge measurement uncertainty."
            )
        else:
            return (
                f"✓ Mean correlation {mean_corr:.2f} (≥ 0.7).\n"
                "Tri-judge ensemble shows good inter-rater reliability.\n"
                "RECOMMENDATION: Proceed with publication, report IRR scores in methods."
            )


def main():
    """CLI entry point for IRR analysis."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Calculate inter-rater reliability for tri-judge ensemble"
    )
    parser.add_argument(
        "--results",
        type=Path,
        required=True,
        help="Path to benchmark results JSON"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/results/irr_analysis.json"),
        help="Where to save IRR analysis results"
    )
    parser.add_argument(
        "--heatmap",
        type=Path,
        default=Path("data/results/judge_agreement_heatmap.png"),
        help="Where to save judge agreement heatmap"
    )

    args = parser.parse_args()

    # Run analysis
    analyzer = JudgeIRRAnalyzer()
    results = analyzer.analyze(args.results)

    # Save results
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2))

    logger.info(f"IRR analysis saved to {args.output}")
    logger.info(f"Judge agreement heatmap saved to {args.heatmap}")
    logger.info(f"\n{results['interpretation']}")


if __name__ == "__main__":
    main()
