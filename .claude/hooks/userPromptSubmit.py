#!/usr/bin/env python3
"""
User Prompt Submit Hook - Auto-activates relevant skills based on prompt content
"""
import json
import sys
import re
from pathlib import Path

def load_skill_rules():
    """Load skill activation rules from JSON"""
    rules_path = Path(__file__).parent / "skill-rules.json"
    if not rules_path.exists():
        return {}

    try:
        with open(rules_path) as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading skill rules: {e}", file=sys.stderr)
        return {}

def check_activation(skill_name, rule, user_message, recent_files):
    """Check if a skill should activate based on rules"""
    reasons = []

    # Check keyword triggers
    lower_message = user_message.lower()
    matched_keywords = [
        kw for kw in rule['promptTriggers']['keywords']
        if kw.lower() in lower_message
    ]
    if matched_keywords:
        reasons.append(f"Keywords: {', '.join(matched_keywords[:3])}")

    # Check intent patterns
    for pattern in rule['promptTriggers']['intentPatterns']:
        try:
            if re.search(pattern, user_message, re.IGNORECASE):
                reasons.append("Intent pattern matched")
                break
        except re.error:
            continue

    # Check file triggers
    if recent_files:
        matched_files = []
        for file_path in recent_files:
            for pattern in rule['fileTriggers']['pathPatterns']:
                # Convert glob pattern to regex
                regex_pattern = (
                    pattern
                    .replace('**', '.*')
                    .replace('*', '[^/]*')
                    .replace('.', r'\.')
                )
                try:
                    if re.search(regex_pattern, file_path):
                        matched_files.append(Path(file_path).name)
                        break
                except re.error:
                    continue

        if matched_files:
            reasons.append(f"Files: {', '.join(matched_files[:2])}")

    return reasons

def main():
    # Read input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("Error: Invalid JSON input", file=sys.stderr)
        sys.exit(1)

    user_message = input_data.get('userMessage', '')
    recent_files = input_data.get('recentFiles', [])

    # Load skill rules
    skill_rules = load_skill_rules()
    if not skill_rules:
        # No rules, pass through unchanged
        print(json.dumps({"userMessage": user_message}))
        sys.exit(0)

    # Check each skill for activation
    activated_skills = []
    for skill_name, rule in skill_rules.items():
        reasons = check_activation(skill_name, rule, user_message, recent_files)
        if reasons:
            activated_skills.append({
                'name': skill_name,
                'priority': rule.get('priority', 'medium'),
                'reasons': reasons
            })

    # If no skills activated, pass through unchanged
    if not activated_skills:
        print(json.dumps({"userMessage": user_message}))
        sys.exit(0)

    # Sort by priority
    priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    activated_skills.sort(
        key=lambda s: priority_order.get(s['priority'], 999)
    )

    # Build skill reminder message
    skill_reminder = "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    skill_reminder += "🎯 SKILL ACTIVATION CHECK\n"
    skill_reminder += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    skill_reminder += f"Detected {len(activated_skills)} relevant skill(s) for this task:\n\n"

    for idx, skill in enumerate(activated_skills, 1):
        icon = {
            'critical': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '⚪'
        }.get(skill['priority'], '⚪')

        skill_reminder += f"{idx}. {icon} **{skill['name']}** ({skill['priority']} priority)\n"
        skill_reminder += f"   Reason: {', '.join(skill['reasons'])}\n"

    skill_reminder += "\n💡 Please check and use these skills for guidance on:\n"
    skill_reminder += "   - Research grounding and evidence-based design\n"
    skill_reminder += "   - Best practices and established patterns\n"
    skill_reminder += "   - Common pitfalls to avoid\n"
    skill_reminder += "   - Documentation and validation requirements\n"

    skill_reminder += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # Return modified message
    modified_message = skill_reminder + user_message
    print(json.dumps({"userMessage": modified_message}))
    sys.exit(0)

if __name__ == '__main__':
    main()
