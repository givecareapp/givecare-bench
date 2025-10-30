"""
Inter-Rater Reliability (IRR) analysis for tri-judge ensemble.

Tests whether the 3 judges agree on their dimension scores across benchmark evaluations.
This is critical for publication - demonstrates that the scoring framework is reliable
and not dependent on a single judge's perspective.

Key metrics:
- Spearman ρ: Rank correlation between judge pairs (range: -1 to 1)
  - ρ > 0.7 required for reliability claims
  - Calculated pairwise for all dimensions
- Cohen's κ: Agreement on autofail decisions (binary, range: -1 to 1)
  - κ > 0.8 indicates strong agreement
  - Corrects for chance agreement

Implementation:
1. Extracts scores from BenchmarkRun JSON results
2. Organizes scores by dimension and judge
3. Calculates pairwise Spearman correlations for each dimension
4. Calculates Cohen's kappa for autofail binary decisions
5. Generates interpretation based on thresholds
6. Optionally creates heatmap visualization (requires matplotlib/seaborn)

Expected JSON structure:
{
  "results": [
    {
      "scenario_id": "...",
      "turn_evaluations": [
        {
          "turn_number": 1,
          "judge_evaluations": [
            {
              "judge_name": "judge_1",
              "dimension_scores": {"memory": 0.8, "trauma": 0.7, ...},
              "autofail_triggered": false
            },
            ...
          ]
        },
        ...
      ]
    },
    ...
  ]
}

Interpretation thresholds:
- min_corr < 0.5: CRITICAL - poor agreement, review judge prompts
- mean_corr < 0.7: WARNING - below reliability threshold, acknowledge uncertainty
- mean_corr ≥ 0.7: GOOD - proceed with publication

Usage:
    python -m supportbench.evaluation.judge_irr_analysis \
        --results data/results/benchmark_run.json \
        --output data/results/irr_analysis.json \
        --heatmap data/results/judge_agreement_heatmap.png

Dependencies:
    Required: numpy, scipy
    Optional: matplotlib, seaborn (for heatmap visualization)
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
        self.judge_names = ["judge_1", "judge_2", "judge_3"]  # Normalized judge identifiers
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
        # 1. Load results from JSON
        if not results_path.exists():
            raise FileNotFoundError(f"Results file not found: {results_path}")

        try:
            with open(results_path, 'r') as f:
                results = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in results file: {e}")

        # 2. Extract judge scores per turn per dimension
        judge_scores = self._extract_judge_scores(results)

        if not judge_scores:
            logger.warning("No judge scores found in results. Results may be incomplete.")
            return {
                "dimension_correlations": {},
                "autofail_kappa": {},
                "mean_correlation": 0.0,
                "min_correlation": 0.0,
                "interpretation": "⚠️  No judge scores found. Results file may be incomplete."
            }

        # 3. Calculate pairwise Spearman ρ for each dimension
        dimension_correlations = {}

        for dimension in self.dimension_names:
            if dimension not in judge_scores:
                continue

            dim_scores = judge_scores[dimension]

            # Need at least 2 judges with scores
            available_judges = [j for j in self.judge_names if j in dim_scores and len(dim_scores[j]) > 0]
            if len(available_judges) < 2:
                continue

            dimension_correlations[dimension] = {}

            # Calculate pairwise correlations
            for i in range(len(available_judges)):
                for j in range(i + 1, len(available_judges)):
                    judge1 = available_judges[i]
                    judge2 = available_judges[j]

                    scores1 = dim_scores[judge1]
                    scores2 = dim_scores[judge2]

                    # Need matching lengths and at least 3 data points for Spearman
                    min_len = min(len(scores1), len(scores2))
                    if min_len < 3:
                        continue

                    # Truncate to matching length
                    scores1_aligned = scores1[:min_len]
                    scores2_aligned = scores2[:min_len]

                    try:
                        corr, p_value = self._calculate_pairwise_correlation(
                            scores1_aligned, scores2_aligned
                        )
                        dimension_correlations[dimension][f"{judge1}_vs_{judge2}"] = corr
                    except Exception as e:
                        logger.warning(f"Failed to calculate correlation for {dimension} {judge1} vs {judge2}: {e}")

        # 4. Calculate Cohen's κ for autofail agreements
        autofail_kappa = {}
        autofails = self._extract_autofail_decisions(results)

        if autofails:
            available_judges = [j for j in self.judge_names if j in autofails and len(autofails[j]) > 0]

            for i in range(len(available_judges)):
                for j in range(i + 1, len(available_judges)):
                    judge1 = available_judges[i]
                    judge2 = available_judges[j]

                    autofails1 = autofails[judge1]
                    autofails2 = autofails[judge2]

                    # Align lengths
                    min_len = min(len(autofails1), len(autofails2))
                    if min_len < 2:
                        continue

                    autofails1_aligned = autofails1[:min_len]
                    autofails2_aligned = autofails2[:min_len]

                    try:
                        kappa = self._calculate_cohens_kappa(autofails1_aligned, autofails2_aligned)
                        autofail_kappa[f"{judge1}_vs_{judge2}"] = kappa
                    except Exception as e:
                        logger.warning(f"Failed to calculate kappa for {judge1} vs {judge2}: {e}")

        # Calculate summary statistics
        all_corrs = []
        for dim_corrs in dimension_correlations.values():
            all_corrs.extend(dim_corrs.values())

        mean_corr = float(np.mean(all_corrs)) if all_corrs else 0.0
        min_corr = float(np.min(all_corrs)) if all_corrs else 0.0

        # 6. Generate interpretation
        interpretation = self._interpret_results(dimension_correlations)

        return {
            "dimension_correlations": dimension_correlations,
            "autofail_kappa": autofail_kappa,
            "mean_correlation": round(mean_corr, 3),
            "min_correlation": round(min_corr, 3),
            "interpretation": interpretation
        }

    def _extract_judge_scores(self, results: Dict) -> Dict[str, Dict[str, List[float]]]:
        """
        Extract judge scores organized by dimension.

        Args:
            results: Loaded benchmark results JSON

        Returns:
            Dict[dimension][judge_name] = list of scores across all turns
        """
        # Initialize structure: dimension -> judge -> scores
        dimension_judge_scores = {dim: {judge: [] for judge in self.judge_names} for dim in self.dimension_names}

        # Handle different result structures
        # Case 1: BenchmarkRun with 'results' key containing ScenarioResults
        if "results" in results and isinstance(results["results"], list):
            scenario_results = results["results"]
        # Case 2: Direct ScenarioResult
        elif "turn_evaluations" in results:
            scenario_results = [results]
        # Case 3: List of ScenarioResults at top level
        elif isinstance(results, list):
            scenario_results = results
        else:
            logger.warning(f"Unrecognized results structure. Keys: {results.keys()}")
            return {}

        # Extract scores from all scenario results
        for scenario_result in scenario_results:
            if not isinstance(scenario_result, dict):
                continue

            turn_evaluations = scenario_result.get("turn_evaluations", [])

            for turn_eval in turn_evaluations:
                if not isinstance(turn_eval, dict):
                    continue

                judge_evaluations = turn_eval.get("judge_evaluations", [])

                for judge_eval in judge_evaluations:
                    if not isinstance(judge_eval, dict):
                        continue

                    judge_name = judge_eval.get("judge_name")
                    if not judge_name:
                        continue

                    # Normalize judge name to match expected format
                    judge_name = judge_name.lower().replace(" ", "_")
                    if not judge_name.startswith("judge_"):
                        # Try to map to judge_1, judge_2, judge_3
                        if "1" in judge_name or "one" in judge_name:
                            judge_name = "judge_1"
                        elif "2" in judge_name or "two" in judge_name:
                            judge_name = "judge_2"
                        elif "3" in judge_name or "three" in judge_name:
                            judge_name = "judge_3"

                    dimension_scores = judge_eval.get("dimension_scores", {})

                    # Extract scores for each dimension
                    for dim_key, score in dimension_scores.items():
                        # Normalize dimension key
                        dim_normalized = dim_key.lower().replace(" ", "_").replace("-", "_")

                        # Map to standard dimension names
                        if dim_normalized in dimension_judge_scores:
                            if judge_name in dimension_judge_scores[dim_normalized]:
                                dimension_judge_scores[dim_normalized][judge_name].append(float(score))

        # Remove empty dimensions
        dimension_judge_scores = {
            dim: judges for dim, judges in dimension_judge_scores.items()
            if any(len(scores) > 0 for scores in judges.values())
        }

        return dimension_judge_scores

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

        Formula: κ = (p_o - p_e) / (1 - p_e)
        Where:
        - p_o = observed agreement
        - p_e = expected agreement by chance

        Args:
            judge1_autofails: Binary autofail decisions from judge 1
            judge2_autofails: Binary autofail decisions from judge 2

        Returns:
            Cohen's κ value (range: -1 to 1, where 1 = perfect agreement)
        """
        if len(judge1_autofails) != len(judge2_autofails):
            raise ValueError("Autofail lists must have same length")

        if len(judge1_autofails) == 0:
            return 0.0

        n = len(judge1_autofails)

        # Convert to numpy arrays for easier computation
        j1 = np.array(judge1_autofails, dtype=int)
        j2 = np.array(judge2_autofails, dtype=int)

        # Calculate observed agreement (p_o)
        agreements = (j1 == j2).sum()
        p_o = agreements / n

        # Calculate expected agreement by chance (p_e)
        # p_e = P(both say yes) + P(both say no)
        # P(both say yes) = P(j1 says yes) * P(j2 says yes)
        # P(both say no) = P(j1 says no) * P(j2 says no)

        p_j1_yes = j1.sum() / n
        p_j1_no = 1 - p_j1_yes
        p_j2_yes = j2.sum() / n
        p_j2_no = 1 - p_j2_yes

        p_e = (p_j1_yes * p_j2_yes) + (p_j1_no * p_j2_no)

        # Calculate Cohen's kappa
        if p_e == 1.0:
            # Perfect chance agreement (degenerate case)
            return 1.0 if p_o == 1.0 else 0.0

        kappa = (p_o - p_e) / (1 - p_e)

        return float(kappa)

    def _extract_autofail_decisions(self, results: Dict) -> Dict[str, List[bool]]:
        """
        Extract autofail decisions from all judges.

        Args:
            results: Loaded benchmark results JSON

        Returns:
            Dict[judge_name] = list of autofail decisions (True/False)
        """
        judge_autofails = {judge: [] for judge in self.judge_names}

        # Handle different result structures
        if "results" in results and isinstance(results["results"], list):
            scenario_results = results["results"]
        elif "turn_evaluations" in results:
            scenario_results = [results]
        elif isinstance(results, list):
            scenario_results = results
        else:
            return {}

        # Extract autofail decisions
        for scenario_result in scenario_results:
            if not isinstance(scenario_result, dict):
                continue

            turn_evaluations = scenario_result.get("turn_evaluations", [])

            for turn_eval in turn_evaluations:
                if not isinstance(turn_eval, dict):
                    continue

                judge_evaluations = turn_eval.get("judge_evaluations", [])

                for judge_eval in judge_evaluations:
                    if not isinstance(judge_eval, dict):
                        continue

                    judge_name = judge_eval.get("judge_name")
                    if not judge_name:
                        continue

                    # Normalize judge name
                    judge_name = judge_name.lower().replace(" ", "_")
                    if not judge_name.startswith("judge_"):
                        if "1" in judge_name or "one" in judge_name:
                            judge_name = "judge_1"
                        elif "2" in judge_name or "two" in judge_name:
                            judge_name = "judge_2"
                        elif "3" in judge_name or "three" in judge_name:
                            judge_name = "judge_3"

                    autofail = judge_eval.get("autofail_triggered", False)

                    if judge_name in judge_autofails:
                        judge_autofails[judge_name].append(bool(autofail))

        return judge_autofails

    def _generate_heatmap(self, correlations: Dict[str, float], output_path: Path):
        """
        Generate heatmap of judge correlations across dimensions.

        Args:
            correlations: Dict of dimension -> correlation value
            output_path: Where to save the heatmap
        """
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns
        except ImportError:
            logger.warning("matplotlib/seaborn not available. Skipping heatmap generation.")
            return

        if not correlations:
            logger.warning("No correlations to plot. Skipping heatmap generation.")
            return

        # Prepare data for heatmap
        # Extract all unique judge pairs
        judge_pairs = set()
        for dim_corrs in correlations.values():
            judge_pairs.update(dim_corrs.keys())

        judge_pairs = sorted(judge_pairs)

        if not judge_pairs:
            logger.warning("No judge pairs found. Skipping heatmap generation.")
            return

        # Create matrix: dimensions × judge pairs
        dimensions = sorted(correlations.keys())
        matrix = np.zeros((len(dimensions), len(judge_pairs)))

        for i, dim in enumerate(dimensions):
            for j, pair in enumerate(judge_pairs):
                matrix[i, j] = correlations[dim].get(pair, 0.0)

        # Create heatmap
        fig, ax = plt.subplots(figsize=(10, 8))

        sns.heatmap(
            matrix,
            xticklabels=judge_pairs,
            yticklabels=dimensions,
            annot=True,
            fmt='.2f',
            cmap='RdYlGn',
            vmin=0,
            vmax=1,
            center=0.7,
            cbar_kws={'label': 'Spearman ρ'},
            ax=ax
        )

        ax.set_title('Judge Agreement Across Dimensions (Spearman ρ)', fontsize=14, fontweight='bold')
        ax.set_xlabel('Judge Pairs', fontsize=12)
        ax.set_ylabel('Evaluation Dimensions', fontsize=12)

        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        plt.tight_layout()

        # Save figure
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"Heatmap saved to {output_path}")

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

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run analysis
    analyzer = JudgeIRRAnalyzer()
    results = analyzer.analyze(args.results)

    # Generate heatmap if correlations are available
    if results.get("dimension_correlations"):
        analyzer._generate_heatmap(results["dimension_correlations"], args.heatmap)

    # Save results
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2))

    logger.info(f"IRR analysis saved to {args.output}")
    if results.get("dimension_correlations"):
        logger.info(f"Judge agreement heatmap saved to {args.heatmap}")
    logger.info(f"\n{results['interpretation']}")

    # Print summary statistics
    print("\n=== Inter-Rater Reliability Summary ===")
    print(f"Mean Correlation: {results['mean_correlation']:.3f}")
    print(f"Min Correlation: {results['min_correlation']:.3f}")
    print(f"\nDimensions Analyzed: {len(results['dimension_correlations'])}")
    if results.get("autofail_kappa"):
        print(f"Autofail Agreement (Cohen's κ): {list(results['autofail_kappa'].values())}")
    print(f"\n{results['interpretation']}")


if __name__ == "__main__":
    main()
