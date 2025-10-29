#!/usr/bin/env python3
"""
Validate HuggingFace dataset structure before upload.

Usage:
    python huggingface/validate_structure.py
"""

from pathlib import Path
import yaml
import json

def validate_structure():
    """Validate that all required files exist and are properly formatted."""

    base_path = Path(__file__).parent.parent  # Project root
    hf_path = Path(__file__).parent  # huggingface/ directory
    errors = []
    warnings = []

    # Required files in root
    required_root_files = [
        "LICENSE",
        "requirements.txt",
    ]

    # Required files in huggingface/
    required_hf_files = [
        "README_HF.md",
        "upload_script.py",
        ".huggingface_ignore",
        "SETUP.md",
    ]

    print("="*60)
    print("HuggingFace Structure Validation")
    print("="*60)

    # Check required root files
    print("\n1. Checking required root files...")
    for file in required_root_files:
        file_path = base_path / file
        if file_path.exists():
            print(f"   ✅ {file}")
        else:
            errors.append(f"Missing required file: {file}")
            print(f"   ❌ {file} - MISSING")

    # Check required HuggingFace files
    print("\n2. Checking required HuggingFace files...")
    for file in required_hf_files:
        file_path = hf_path / file
        if file_path.exists():
            print(f"   ✅ huggingface/{file}")
        else:
            errors.append(f"Missing required file: huggingface/{file}")
            print(f"   ❌ huggingface/{file} - MISSING")

    # Check scenarios directory
    print("\n3. Checking scenarios directory...")
    scenarios_path = base_path / "scenarios"
    if scenarios_path.exists():
        print(f"   ✅ scenarios/ exists")

        # Count scenarios by tier
        tier1 = list(scenarios_path.glob("tier1/**/*.json"))
        tier2 = list(scenarios_path.glob("tier2/**/*.json"))
        tier3 = list(scenarios_path.glob("tier3/**/*.json"))
        confidential = list(scenarios_path.glob("confidential/*.json"))

        print(f"      - Tier 1: {len(tier1)} scenarios")
        print(f"      - Tier 2: {len(tier2)} scenarios")
        print(f"      - Tier 3: {len(tier3)} scenarios")
        print(f"      - Confidential: {len(confidential)} scenarios")

        total = len(tier1) + len(tier2) + len(tier3)
        if total == 0:
            warnings.append("No scenarios found in tier1/tier2/tier3")
    else:
        errors.append("scenarios/ directory not found")
        print(f"   ❌ scenarios/ - MISSING")

    # Check rules directory
    print("\n3. Checking rules directory...")
    rules_path = base_path / "supportbench" / "rules"
    if rules_path.exists():
        print(f"   ✅ supportbench/rules/ exists")

        rule_files = list(rules_path.glob("*.yaml"))
        print(f"      - Found {len(rule_files)} rule files:")
        for rule_file in rule_files:
            print(f"        • {rule_file.name}")

            # Validate YAML
            try:
                with open(rule_file) as f:
                    yaml.safe_load(f)
                print(f"          ✅ Valid YAML")
            except Exception as e:
                errors.append(f"Invalid YAML in {rule_file.name}: {e}")
                print(f"          ❌ Invalid YAML: {e}")
    else:
        errors.append("supportbench/rules/ directory not found")
        print(f"   ❌ supportbench/rules/ - MISSING")

    # Check configs
    print("\n4. Checking configs...")
    configs_path = base_path / "configs"
    if configs_path.exists():
        scoring_config = configs_path / "scoring.yaml"
        if scoring_config.exists():
            print(f"   ✅ configs/scoring.yaml exists")

            # Validate YAML
            try:
                with open(scoring_config) as f:
                    config = yaml.safe_load(f)
                    if "dimensions" in config:
                        print(f"      - Dimensions: {len(config['dimensions'])}")
                    print(f"      ✅ Valid YAML")
            except Exception as e:
                errors.append(f"Invalid YAML in scoring.yaml: {e}")
                print(f"      ❌ Invalid YAML: {e}")
        else:
            warnings.append("configs/scoring.yaml not found")
            print(f"   ⚠️  configs/scoring.yaml - MISSING")
    else:
        warnings.append("configs/ directory not found")
        print(f"   ⚠️  configs/ - MISSING")

    # Check README_HF metadata
    print("\n5. Validating README_HF.md metadata...")
    readme_path = hf_path / "README_HF.md"
    if readme_path.exists():
        with open(readme_path) as f:
            content = f.read()

            # Check for YAML frontmatter
            if content.startswith("---"):
                try:
                    # Extract frontmatter
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1])

                        # Check required fields
                        required_fields = ["license", "task_categories", "language"]
                        for field in required_fields:
                            if field in frontmatter:
                                print(f"   ✅ {field}: {frontmatter[field]}")
                            else:
                                errors.append(f"Missing required field in README metadata: {field}")
                                print(f"   ❌ {field} - MISSING")
                    else:
                        errors.append("README_HF.md has invalid frontmatter structure")
                        print(f"   ❌ Invalid frontmatter structure")
                except Exception as e:
                    errors.append(f"Invalid YAML frontmatter in README_HF.md: {e}")
                    print(f"   ❌ Invalid frontmatter: {e}")
            else:
                errors.append("README_HF.md missing YAML frontmatter")
                print(f"   ❌ Missing frontmatter")

    # Summary
    print("\n" + "="*60)
    print("Validation Summary")
    print("="*60)

    if errors:
        print(f"\n❌ {len(errors)} ERROR(S) FOUND:")
        for error in errors:
            print(f"   • {error}")

    if warnings:
        print(f"\n⚠️  {len(warnings)} WARNING(S):")
        for warning in warnings:
            print(f"   • {warning}")

    if not errors and not warnings:
        print("\n✅ All validation checks passed!")
        print("\nNext steps:")
        print("1. Get HuggingFace token: https://huggingface.co/settings/tokens")
        print("2. Run: python huggingface/upload_script.py --token YOUR_TOKEN")
    elif not errors:
        print("\n✅ No critical errors found!")
        print("⚠️  Warnings can be ignored, but review them before upload.")
        print("\nNext steps:")
        print("1. Get HuggingFace token: https://huggingface.co/settings/tokens")
        print("2. Run: python huggingface/upload_script.py --token YOUR_TOKEN")
    else:
        print("\n❌ Fix errors before uploading to HuggingFace")
        return 1

    return 0

if __name__ == "__main__":
    exit(validate_structure())
