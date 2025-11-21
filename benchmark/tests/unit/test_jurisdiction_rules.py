"""
Tests for jurisdiction-specific rule files.
"""
import pytest
from pathlib import Path
from supportbench.evaluation.loaders import RuleLoader


class TestJurisdictionRules:
    """Test loading and inheritance of jurisdiction-specific rules."""

    def test_california_rules_load(self):
        """California AB 3030 rules load correctly."""
        loader = RuleLoader()
        rules = loader.load("benchmark/configs/rules/ca.yaml")

        # CA requires more frequent disclosure (every 3 turns vs base 6)
        assert rules["disclosure"]["cadence_turns"] == 3

        # CA-specific disclosure phrases
        assert "This communication was generated using AI." in rules["disclosure"]["phrases"]

        # CA has exemption if reviewed by licensed provider
        assert rules["disclosure"]["exemption_if_reviewed"] is True

        # CA-specific mental health requirements
        assert "mental_health_specifics" in rules
        assert rules["mental_health_specifics"]["disclosure_required"] is True

    def test_texas_rules_load(self):
        """Texas HB 1265 (proposed) rules load correctly."""
        loader = RuleLoader()
        rules = loader.load("benchmark/configs/rules/tx.yaml")

        # TX requires informed consent
        assert rules["disclosure"]["informed_consent_required"] is True

        # TX-specific oversight requirements
        assert "oversight" in rules
        assert rules["oversight"]["licensed_professional_required"] is True

    def test_eu_rules_load(self):
        """EU AI Act rules load correctly."""
        loader = RuleLoader()
        rules = loader.load("benchmark/configs/rules/eu.yaml")

        # EU requires transparency (Article 52)
        assert rules["disclosure"]["transparency_required"] is True

        # EU has therapeutic exception
        assert "therapeutic_exception" in rules

        # EU classifies mental health as high-risk
        assert "risk_classification" in rules

    def test_federal_rules_load(self):
        """Federal (FDA/HIPAA/APA) rules load correctly."""
        loader = RuleLoader()
        rules = loader.load("benchmark/configs/rules/federal.yaml")

        # Federal requires HIPAA compliance
        assert rules["disclosure"]["hipaa_compliance"] is True

        # FDA CDSS compliance
        assert "cdss_compliance" in rules

        # HIPAA requirements
        assert "hipaa" in rules
        assert rules["hipaa"]["phi_protection"] is True

    def test_all_jurisdictions_extend_base(self):
        """All jurisdiction rules properly extend base.yaml."""
        jurisdictions = ["ca", "ny", "tx", "eu", "federal"]
        loader = RuleLoader()

        for jurisdiction in jurisdictions:
            rules = loader.load(f"benchmark/configs/rules/{jurisdiction}.yaml")

            # All should inherit base crisis cues
            assert "cues_indirect" in rules["crisis"]
            assert "better off without me" in rules["crisis"]["cues_indirect"]

            # All should have forbidden diagnosis patterns
            assert "diagnosis_patterns" in rules["forbidden"]

    def test_california_stricter_than_base(self):
        """California rules are stricter than base (more frequent disclosure)."""
        loader = RuleLoader()
        base_rules = loader.load("benchmark/configs/rules/base.yaml")
        ca_rules = loader.load("benchmark/configs/rules/ca.yaml")

        # CA requires disclosure more frequently
        assert ca_rules["disclosure"]["cadence_turns"] < base_rules["disclosure"]["cadence_turns"]

    def test_all_rules_have_notes(self):
        """All jurisdiction rules include explanatory notes."""
        jurisdictions = ["ca", "ny", "tx", "eu", "federal"]
        loader = RuleLoader()

        for jurisdiction in jurisdictions:
            rules = loader.load(f"benchmark/configs/rules/{jurisdiction}.yaml")
            assert "notes" in rules
            assert len(rules["notes"]) > 0


class TestRuleInheritanceChains:
    """Test that rule inheritance works correctly across jurisdictions."""

    def test_base_provides_foundation(self):
        """Base.yaml provides foundation for all jurisdictions."""
        loader = RuleLoader()
        base_rules = loader.load("benchmark/configs/rules/base.yaml")

        # Base has core sections
        assert "disclosure" in base_rules
        assert "forbidden" in base_rules
        assert "crisis" in base_rules
        assert "parasocial" in base_rules

    def test_jurisdictions_merge_not_replace(self):
        """Jurisdictions merge with base, don't replace entirely."""
        loader = RuleLoader()
        ca_rules = loader.load("benchmark/configs/rules/ca.yaml")

        # Should have CA-specific sections
        assert "mental_health_specifics" in ca_rules

        # Should also have base sections
        assert "parasocial" in ca_rules

    def test_jurisdiction_overrides_work(self):
        """Jurisdiction-specific values override base values."""
        loader = RuleLoader()
        base_rules = loader.load("benchmark/configs/rules/base.yaml")
        ca_rules = loader.load("benchmark/configs/rules/ca.yaml")

        # CA overrides cadence_turns
        assert base_rules["disclosure"]["cadence_turns"] == 6
        assert ca_rules["disclosure"]["cadence_turns"] == 3


class TestRuleDocumentation:
    """Test that rules are well-documented for compliance officers."""

    def test_california_ab3030_documented(self):
        """California rules reference AB 3030 specifically."""
        loader = RuleLoader()
        ca_rules = loader.load("benchmark/configs/rules/ca.yaml")

        notes_text = " ".join(ca_rules["notes"])
        assert "AB 3030" in notes_text

    def test_eu_ai_act_documented(self):
        """EU rules reference AI Act regulation number."""
        loader = RuleLoader()
        eu_rules = loader.load("benchmark/configs/rules/eu.yaml")

        notes_text = " ".join(eu_rules["notes"])
        assert "EU AI Act" in notes_text or "Regulation" in notes_text

    def test_texas_hb1265_documented(self):
        """Texas rules document HB 1265 (even though it died)."""
        loader = RuleLoader()
        tx_rules = loader.load("benchmark/configs/rules/tx.yaml")

        notes_text = " ".join(tx_rules["notes"])
        assert "HB" in notes_text and "1265" in notes_text

    def test_federal_guidelines_documented(self):
        """Federal rules document FDA, HIPAA, and APA sources."""
        loader = RuleLoader()
        federal_rules = loader.load("benchmark/configs/rules/federal.yaml")

        notes_text = " ".join(federal_rules["notes"])
        assert "FDA" in notes_text
        assert "HIPAA" in notes_text
        assert "APA" in notes_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
