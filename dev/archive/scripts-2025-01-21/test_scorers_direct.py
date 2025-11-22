#!/usr/bin/env python3
"""
Direct test of updated Belonging and Trauma scorers.
Bypasses orchestrator to test scorer functions directly.
"""

import json
import jsonlines
import sys
from pathlib import Path

# Add benchmark to path
sys.path.insert(0, str(Path(__file__).parent / "benchmark"))

from invisiblebench.evaluation.scorers import belonging, trauma
from invisiblebench.api.client import ModelAPIClient


def load_transcript(transcript_path: Path) -> list:
    """Load transcript from JSONL file."""
    with jsonlines.open(transcript_path, 'r') as reader:
        return list(reader)


def test_scorer(scorer_name: str, transcript: list, api_client: ModelAPIClient):
    """Test a single scorer."""
    print(f"\n{'='*60}")
    print(f"Testing {scorer_name} Scorer")
    print(f"{'='*60}")

    if scorer_name == "belonging":
        result = belonging.score(
            transcript=transcript,
            scenario={},
            api_client=api_client
        )
    elif scorer_name == "trauma":
        result = trauma.score(
            transcript=transcript,
            scenario={},
            api_client=api_client
        )
    else:
        print(f"Unknown scorer: {scorer_name}")
        return None

    print(f"\n📊 Score: {result['score']:.3f}")
    print(f"\n📋 Breakdown:")
    for key, value in result['breakdown'].items():
        print(f"  {key}: {value:.3f}")

    print(f"\n📝 Evidence (first 500 chars):")
    if result.get('evidence'):
        evidence_text = '\n'.join(result['evidence'][:2])
        print(evidence_text[:500])
        if len(evidence_text) > 500:
            print("... (truncated)")

    return result


def main():
    print("="*80)
    print("DIRECT SCORER TEST - BELONGING & TRAUMA")
    print("="*80)

    # Initialize API client
    print("\n🔧 Initializing API client...")
    try:
        api_client = ModelAPIClient()
        print("✅ API client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize API client: {e}")
        return 1

    # Load one transcript for testing
    transcript_path = Path("results/full_validation/transcripts/anthropic_claude-sonnet-4.5_tier1_crisis_001.jsonl")

    if not transcript_path.exists():
        print(f"\n❌ Transcript not found: {transcript_path}")
        return 1

    print(f"\n📄 Loading transcript: {transcript_path.name}")
    try:
        transcript = load_transcript(transcript_path)
        print(f"✅ Loaded {len(transcript)} messages")
    except Exception as e:
        print(f"❌ Failed to load transcript: {e}")
        return 1

    # Test Belonging scorer
    try:
        belonging_result = test_scorer("belonging", transcript, api_client)
    except Exception as e:
        print(f"\n❌ Belonging scorer failed: {e}")
        import traceback
        traceback.print_exc()
        belonging_result = None

    # Test Trauma scorer
    try:
        trauma_result = test_scorer("trauma", transcript, api_client)
    except Exception as e:
        print(f"\n❌ Trauma scorer failed: {e}")
        import traceback
        traceback.print_exc()
        trauma_result = None

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    if belonging_result:
        print(f"\n✅ Belonging Scorer: {belonging_result['score']:.3f}")
        print(f"   Recognition: {belonging_result['breakdown'].get('recognition', 0.0):.2f}")
        print(f"   Agency: {belonging_result['breakdown'].get('agency', 0.0):.2f}")
        print(f"   Connection: {belonging_result['breakdown'].get('connection', 0.0):.2f}")
        print(f"   Penalties: {belonging_result['breakdown'].get('explicit_othering_penalty', 0.0):.2f} + "
              f"{belonging_result['breakdown'].get('implicit_stereotyping_penalty', 0.0):.2f} + "
              f"{belonging_result['breakdown'].get('power_over_penalty', 0.0):.2f} + "
              f"{belonging_result['breakdown'].get('individual_blame_penalty', 0.0):.2f}")
    else:
        print("\n❌ Belonging Scorer: FAILED")

    if trauma_result:
        print(f"\n✅ Trauma Scorer: {trauma_result['score']:.3f}")
        print(f"   Original dimensions (40% weight):")
        print(f"     Skill Correctness: {trauma_result['breakdown'].get('skill_correctness', 0.0):.2f}")
        print(f"     Grounding: {trauma_result['breakdown'].get('grounding_before_advice', 0.0):.2f}")
        print(f"     Boundaries: {trauma_result['breakdown'].get('boundary_integrity', 0.0):.2f}")
        print(f"   Trauma-informed principles (60% weight):")
        print(f"     Safety & Predictability: {trauma_result['breakdown'].get('safety_predictability', 0.0):.2f}")
        print(f"     Trust & Transparency: {trauma_result['breakdown'].get('trust_transparency', 0.0):.2f}")
        print(f"     Choice & Control: {trauma_result['breakdown'].get('choice_control', 0.0):.2f}")
        print(f"     Empowerment & Agency: {trauma_result['breakdown'].get('empowerment_agency', 0.0):.2f}")
        print(f"     Collaboration & Community: {trauma_result['breakdown'].get('collaboration_community', 0.0):.2f}")
        print(f"     Cultural Sensitivity: {trauma_result['breakdown'].get('cultural_sensitivity', 0.0):.2f}")
        print(f"     Flexibility & Adaptability: {trauma_result['breakdown'].get('flexibility_adaptability', 0.0):.2f}")
    else:
        print("\n❌ Trauma Scorer: FAILED")

    print(f"\n{'='*80}")

    # Save results
    if belonging_result or trauma_result:
        output = {
            "belonging": belonging_result,
            "trauma": trauma_result
        }
        output_file = Path("direct_scorer_test_results.json")
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"Results saved to: {output_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
