#!/usr/bin/env python3
"""
Extract useful caregiver data from Reddit r/CaregiverSupport posts.

Ethical considerations:
- Do NOT use posts verbatim in scenarios
- Extract patterns, themes, language only
- Anonymize any identifying details
- Use as inspiration, not direct content
"""

import json
import re
from typing import Dict, List
from datetime import datetime


def clean_html_entities(text: str) -> str:
    """Remove HTML entities and formatting."""
    if not text:
        return ""

    # HTML entities
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")

    # Remove HTML comments
    text = re.sub(r'<!-- SC_OFF -->.*?<!-- SC_ON -->', '', text, flags=re.DOTALL)

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    return text.strip()


def extract_crisis_signals(text: str) -> List[str]:
    """Identify crisis indicators in post."""
    signals = []
    text_lower = text.lower()

    crisis_patterns = [
        ("suicidal_ideation", r"(kill myself|end my life|off myself|don't want to live|can't go on)"),
        ("self_harm", r"(hurt myself|harm|cutting)"),
        ("breakdown", r"(can't cope|breaking point|can't do this|losing my mind)"),
        ("exhaustion", r"(haven't slept|exhausted|burnt out|no energy|can't function)"),
        ("isolation", r"(no one to talk to|alone|isolated|no support)"),
    ]

    for signal_type, pattern in crisis_patterns:
        if re.search(pattern, text_lower):
            signals.append(signal_type)

    return signals


def extract_relationships(text: str) -> Dict[str, str]:
    """Extract caregiver-recipient relationship."""
    relationships = {}
    text_lower = text.lower()

    # Common patterns
    if re.search(r'(my )?(mother|mom|ma)\b', text_lower):
        relationships['recipient'] = 'mother'
    elif re.search(r'(my )?(father|dad)\b', text_lower):
        relationships['recipient'] = 'father'
    elif re.search(r'(my )?(husband|wife|spouse|partner)\b', text_lower):
        relationships['recipient'] = 'spouse/partner'
    elif re.search(r'(my )?(son|daughter|child)\b', text_lower):
        relationships['recipient'] = 'child'

    # Extract age if mentioned
    age_match = re.search(r'\b(\d{1,2})[MFmf]?\b', text)
    if age_match:
        relationships['caregiver_age'] = age_match.group(1)

    return relationships


def extract_conditions(text: str) -> List[str]:
    """Extract medical conditions mentioned."""
    conditions = []
    text_lower = text.lower()

    condition_patterns = {
        "dementia": r"dementia|alzheimer",
        "stroke": r"stroke",
        "cancer": r"cancer|tumor|oncologist",
        "disability": r"disabled|disability|wheelchair",
        "mental_health": r"depression|anxiety|mental health",
        "chronic_pain": r"chronic pain|pain management",
        "autism": r"autism|asd",
        "terminal": r"terminal|hospice|palliative",
    }

    for condition, pattern in condition_patterns.items():
        if re.search(pattern, text_lower):
            conditions.append(condition)

    return conditions


def extract_pressure_zones(text: str) -> List[str]:
    """Identify pressure zones/stressors."""
    zones = []
    text_lower = text.lower()

    patterns = {
        "financial_strain": r"(can't afford|money|bills|insurance|disability claim|financial)",
        "isolation": r"(alone|isolated|no support|no friends|can't see)",
        "family_conflict": r"(sibling|brother|sister won't help|family conflict)",
        "job_loss": r"(lost my job|quit|had to leave work|retired early)",
        "facility_care": r"(nursing home|facility|assisted living|hospice)",
        "medical_system": r"(doctor|hospital|medicare|insurance denied)",
        "cultural_pressure": r"(cultural|expected to|community judgment|family tradition)",
    }

    for zone, pattern in patterns.items():
        if re.search(pattern, text_lower):
            zones.append(zone)

    return zones


def extract_post_data(post: Dict) -> Dict:
    """Extract useful data from single Reddit post."""
    data = post.get('data', {})

    title = data.get('title', '')
    selftext = clean_html_entities(data.get('selftext', ''))

    # Skip if empty, moderator post, or weekly thread
    if not selftext or data.get('distinguished') == 'moderator':
        return None

    if any(skip in title.lower() for skip in ['weekly', 'megathread', 'sunday reset', 'roll call']):
        return None

    return {
        "title": title,
        "text": selftext,
        "created_utc": datetime.fromtimestamp(data.get('created_utc', 0)).isoformat(),
        "num_comments": data.get('num_comments', 0),
        "crisis_signals": extract_crisis_signals(title + " " + selftext),
        "relationships": extract_relationships(title + " " + selftext),
        "conditions": extract_conditions(title + " " + selftext),
        "pressure_zones": extract_pressure_zones(title + " " + selftext),
        "url": f"https://reddit.com{data.get('permalink', '')}",
    }


def process_reddit_data(reddit_json: Dict) -> List[Dict]:
    """Process raw Reddit JSON and extract useful posts."""
    posts = reddit_json.get('data', {}).get('children', [])

    extracted = []
    for post in posts:
        post_data = extract_post_data(post)
        if post_data:
            extracted.append(post_data)

    return extracted


def generate_scenario_templates(posts: List[Dict]) -> List[Dict]:
    """Generate scenario templates from extracted posts."""
    templates = []

    for post in posts:
        # Only use high-signal posts (has crisis indicators or multiple pressure zones)
        if not post['crisis_signals'] and len(post['pressure_zones']) < 2:
            continue

        template = {
            "inspiration_source": "reddit_caregiver_support",
            "note": "TEMPLATE ONLY - Do not use verbatim. Rewrite with different names, details, contexts",
            "persona_hints": {
                "relationship": post['relationships'].get('recipient', 'unknown'),
                "age_range": post['relationships'].get('caregiver_age', 'unknown'),
                "conditions": post['conditions'],
            },
            "pressure_zones": post['pressure_zones'],
            "crisis_level": "high" if post['crisis_signals'] else "medium",
            "language_patterns": [
                # Extract 2-3 sentence fragments for authentic voice
                # (manual extraction needed)
            ],
            "scenario_category": determine_category(post),
        }

        templates.append(template)

    return templates


def determine_category(post: Dict) -> str:
    """Map to benchmark category."""
    if "suicidal_ideation" in post['crisis_signals'] or "self_harm" in post['crisis_signals']:
        return "crisis_safety"
    elif "cultural_pressure" in post['pressure_zones']:
        return "belonging_cultural_fitness"
    elif "breakdown" in post['crisis_signals'] or "exhaustion" in post['crisis_signals']:
        return "trauma_informed_flow"
    elif "family_conflict" in post['pressure_zones']:
        return "relational_quality"
    else:
        return "actionable_support"


if __name__ == "__main__":
    # Example usage
    with open('reddit_caregivers_clean.json', 'r') as f:
        reddit_data = json.load(f)

    posts = process_reddit_data(reddit_data)

    print(f"Extracted {len(posts)} usable posts")
    print(f"\nCrisis posts: {sum(1 for p in posts if p['crisis_signals'])}")
    print(f"Multi-pressure posts: {sum(1 for p in posts if len(p['pressure_zones']) >= 2)}")

    # Save processed data
    with open('reddit_caregivers_processed.json', 'w') as f:
        json.dump(posts, f, indent=2)

    # Generate templates
    templates = generate_scenario_templates(posts)
    with open('scenario_templates_from_reddit.json', 'w') as f:
        json.dump(templates, f, indent=2)

    print(f"\nGenerated {len(templates)} scenario templates")
