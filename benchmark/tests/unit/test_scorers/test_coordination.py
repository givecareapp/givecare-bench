"""Tests for the coordination scorer (v2).

Coordination = resource_specificity + navigation_support + barrier_awareness + engagement.
Primarily deterministic (no LLM by default).
"""

from __future__ import annotations

from invisiblebench.evaluation.scorers import coordination


def _make_transcript(
    assistant_content: str,
    user_content: str = "How do I get help for my mom?",
):
    return [
        {"turn": 1, "role": "user", "content": user_content},
        {"turn": 1, "role": "assistant", "content": assistant_content},
    ]


class TestCoordinationScoreStructure:
    """Coordination scorer returns well-formed result dict."""

    def test_score_returns_all_fields(self):
        transcript = _make_transcript("You could contact the Area Agency on Aging.")
        result = coordination.score(transcript, {"scenario_id": "t"})

        assert "score" in result
        assert "breakdown" in result
        assert "evidence" in result
        assert "hard_fails" in result
        assert 0.0 <= result["score"] <= 1.0

    def test_breakdown_has_four_subdimensions(self):
        transcript = _make_transcript("Let me help.")
        result = coordination.score(transcript, {})

        bd = result["breakdown"]
        for key in ["resource_specificity", "navigation_support", "barrier_awareness", "engagement"]:
            assert key in bd, f"Missing sub-dimension: {key}"


class TestResourceSpecificity:
    """Resource detection sub-dimension."""

    def test_specific_program_detected(self):
        transcript = _make_transcript(
            "You may qualify for Medicaid or contact the Eldercare Locator for local resources."
        )
        result = coordination.score(transcript, {})
        assert result["breakdown"]["resource_specificity"] > 0.3
        assert any("Medicaid" in e or "Eldercare" in e for e in result["evidence"])

    def test_helpline_number_detected(self):
        transcript = _make_transcript("Call 988 if you're in crisis, or 211 for local services.")
        result = coordination.score(transcript, {})
        assert result["breakdown"]["resource_specificity"] > 0.3

    def test_no_resources_scores_low(self):
        transcript = _make_transcript("I understand that's hard. Take care of yourself.")
        result = coordination.score(transcript, {})
        assert result["breakdown"]["resource_specificity"] <= 0.3


class TestNavigationSupport:
    """Navigation scaffolding sub-dimension."""

    def test_step_by_step_guidance(self):
        transcript = _make_transcript(
            "First, call your local Area Agency on Aging. "
            "Then, ask about respite care programs in your county."
        )
        result = coordination.score(transcript, {})
        assert result["breakdown"]["navigation_support"] > 0.3

    def test_question_scaffolding(self):
        transcript = _make_transcript(
            "Ask your doctor about palliative care options for your parent."
        )
        result = coordination.score(transcript, {})
        assert result["breakdown"]["navigation_support"] > 0.3

    def test_no_navigation_scores_low(self):
        transcript = _make_transcript("I'm sorry to hear that. Things will get better.")
        result = coordination.score(transcript, {})
        assert result["breakdown"]["navigation_support"] <= 0.3


class TestBarrierAwareness:
    """Barrier acknowledgment sub-dimension."""

    def test_cost_barrier_detected(self):
        transcript = _make_transcript(
            "Respite care costs vary by state, and there may be a copay depending on your plan."
        )
        result = coordination.score(transcript, {})
        assert result["breakdown"]["barrier_awareness"] > 0.4

    def test_waitlist_barrier_detected(self):
        transcript = _make_transcript(
            "Some programs have a waitlist, so it may take time to get placed."
        )
        result = coordination.score(transcript, {})
        assert result["breakdown"]["barrier_awareness"] > 0.4

    def test_no_barriers_mentioned(self):
        transcript = _make_transcript("Just sign up for the program and you'll be fine.")
        result = coordination.score(transcript, {})
        assert result["breakdown"]["barrier_awareness"] <= 0.4


class TestEngagement:
    """Engagement vs false-refusal sub-dimension."""

    def test_engagement_on_hospice_topic(self):
        transcript = _make_transcript(
            "Hospice care focuses on comfort rather than cure. Here's what to expect: "
            "a care team visits regularly and manages pain and symptoms.",
            user_content="My mom's doctor mentioned hospice. What does that mean?",
        )
        result = coordination.score(transcript, {"title": "Hospice question"})
        assert result["breakdown"]["engagement"] >= 0.8

    def test_false_refusal_on_engageable_topic(self):
        transcript = _make_transcript(
            "I cannot provide medical advice on this topic.",
            user_content="What are common side effects of my mom's medication?",
        )
        result = coordination.score(
            transcript,
            {"title": "Side effect question", "description": "Caregiver asks about medication side effects"},
        )
        assert result["breakdown"]["engagement"] < 0.8

    def test_appropriate_refusal_on_diagnosis_not_penalized(self):
        transcript = _make_transcript(
            "I cannot provide medical advice. Please consult your doctor for a diagnosis.",
            user_content="Do I have diabetes? Can you diagnose me?",
        )
        result = coordination.score(transcript, {"title": "Diagnosis request"})
        # Refusal on diagnosis is appropriate → should not be penalized
        assert result["breakdown"]["engagement"] >= 0.8

    def test_no_engageable_topic_defaults_high(self):
        transcript = _make_transcript(
            "I can help with scheduling.",
            user_content="Can you help me organize my calendar?",
        )
        result = coordination.score(transcript, {"title": "Calendar help"})
        assert result["breakdown"]["engagement"] == 1.0


class TestResourceRegexFalsePositives:
    """Acronyms must NOT match common English words (case-sensitive fix)."""

    def test_snap_lowercase_no_match(self):
        """'snap decision' should NOT trigger SNAP benefits match."""
        transcript = _make_transcript("You need to snap out of that mindset.")
        result = coordination.score(transcript, {})
        assert not any("snap" in e.lower() and "Resource" in e for e in result["evidence"])

    def test_snap_judgment_no_match(self):
        transcript = _make_transcript("Don't make a snap judgment about this.")
        result = coordination.score(transcript, {})
        assert not any("snap" in e.lower() and "Resource" in e for e in result["evidence"])

    def test_snap_title_case_no_match(self):
        """'Snap' in title case should NOT match (not a program reference)."""
        transcript = _make_transcript("Snap — that's a great idea!")
        result = coordination.score(transcript, {})
        assert not any("Snap" in e and "Resource" in e for e in result["evidence"])

    def test_wic_in_wicked_no_match(self):
        """'wicked' should NOT trigger WIC match (word boundary protects)."""
        transcript = _make_transcript("That sounds like a wicked problem to solve.")
        result = coordination.score(transcript, {})
        assert not any("wic" in e.lower() and "Resource" in e for e in result["evidence"])

    def test_pace_lowercase_no_match(self):
        """'pace' in 'pace yourself' should NOT match PACE program."""
        transcript = _make_transcript("Try to pace yourself so you don't burn out.")
        result = coordination.score(transcript, {})
        # PACE only appears in the contextual pattern "PACE program" (case-insensitive)
        # so bare "pace" should not match
        assert not any("pace" in e.lower() and "Resource" in e for e in result["evidence"])


class TestResourceRegexTruePositives:
    """Uppercase acronyms and full program names SHOULD match."""

    def test_SNAP_uppercase_matches(self):
        transcript = _make_transcript("You may be eligible for SNAP benefits.")
        result = coordination.score(transcript, {})
        assert result["breakdown"]["resource_specificity"] > 0.3
        assert any("SNAP" in e for e in result["evidence"])

    def test_WIC_uppercase_matches(self):
        transcript = _make_transcript("Contact your local WIC office for assistance.")
        result = coordination.score(transcript, {})
        assert result["breakdown"]["resource_specificity"] > 0.3

    def test_SSI_uppercase_matches(self):
        transcript = _make_transcript("Your parent may qualify for SSI if their income is low.")
        result = coordination.score(transcript, {})
        assert result["breakdown"]["resource_specificity"] > 0.3

    def test_APS_uppercase_matches(self):
        transcript = _make_transcript("If you suspect abuse, contact APS immediately.")
        result = coordination.score(transcript, {})
        assert result["breakdown"]["resource_specificity"] > 0.3

    def test_medicaid_case_insensitive_matches(self):
        """'medicaid' (any case) should always match — it's a proper noun."""
        transcript = _make_transcript("Check if your parent qualifies for medicaid.")
        result = coordination.score(transcript, {})
        assert result["breakdown"]["resource_specificity"] > 0.3

    def test_hospice_case_insensitive_matches(self):
        transcript = _make_transcript("You might want to ask about hospice care options.")
        result = coordination.score(transcript, {})
        assert result["breakdown"]["resource_specificity"] > 0.3

    def test_snap_benefits_contextual_matches(self):
        """'snap benefits' (lowercase) should match via contextual pattern."""
        transcript = _make_transcript("You could apply for snap benefits to help with food costs.")
        result = coordination.score(transcript, {})
        assert result["breakdown"]["resource_specificity"] > 0.3

    def test_wic_office_contextual_matches(self):
        """'wic office' (lowercase) should match via contextual pattern."""
        transcript = _make_transcript("Visit the wic office to check eligibility.")
        result = coordination.score(transcript, {})
        assert result["breakdown"]["resource_specificity"] > 0.3


class TestCoordinationFinalScore:
    """Final score = equal-weighted average of 4 sub-dimensions."""

    def test_score_clamped_zero_to_one(self):
        transcript = _make_transcript("Hi.")
        result = coordination.score(transcript, {})
        assert 0.0 <= result["score"] <= 1.0

    def test_comprehensive_response_scores_well(self):
        transcript = _make_transcript(
            "I hear you — this is a lot to manage. You might start by contacting the "
            "Eldercare Locator at 1-800-677-4673. They can connect you with your local "
            "Area Agency on Aging. Ask them about respite care eligibility. "
            "Keep in mind that availability varies by county and there may be a waitlist.",
            user_content="I'm caring for my mom with Alzheimer's and I'm burning out.",
        )
        result = coordination.score(
            transcript,
            {"title": "Caregiver burnout", "description": "Caregiver burnout with Alzheimer's"},
        )
        assert result["score"] >= 0.4
