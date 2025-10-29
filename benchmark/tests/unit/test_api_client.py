#!/usr/bin/env python3
"""
Quick API test to verify OpenRouter/OpenAI connectivity.
Run this before the full benchmark to ensure API keys work.
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_api_keys():
    """Check if API keys are set."""
    print("Checking API keys...")

    keys = {
        "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
    }

    for key_name, key_value in keys.items():
        if key_value and key_value != "your_key_here":
            print(f"  ✓ {key_name}: configured")
        else:
            print(f"  ✗ {key_name}: missing or placeholder")

    return any(v and v != "your_key_here" for v in keys.values())

def test_openrouter_call():
    """Test a simple OpenRouter API call."""
    import requests

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key.startswith("your_"):
        print("\n✗ OpenRouter API key not configured")
        return False

    print("\nTesting OpenRouter API call...")

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/givecare/longitudinalbench",
                "X-Title": "LongitudinalBench Test"
            },
            json={
                "model": "openai/gpt-4o-mini",  # Cheap model for testing
                "messages": [
                    {"role": "user", "content": "Say 'API test successful' and nothing else."}
                ],
                "max_tokens": 10
            },
            timeout=30
        )

        response.raise_for_status()
        data = response.json()

        if "choices" in data and len(data["choices"]) > 0:
            message = data["choices"][0]["message"]["content"]
            print(f"  ✓ Response: {message}")
            print(f"  ✓ Tokens used: {data.get('usage', {}).get('total_tokens', 'N/A')}")
            return True
        else:
            print(f"  ✗ Unexpected response format: {data}")
            return False

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_scenario_loading():
    """Test scenario loading."""
    import json
    from pathlib import Path

    print("\nTesting scenario loading...")

    scenario_dir = Path("./scenarios")
    if not scenario_dir.exists():
        print(f"  ✗ Scenario directory not found: {scenario_dir}")
        return False

    scenarios = list(scenario_dir.glob("*.json"))
    print(f"  ✓ Found {len(scenarios)} scenario files")

    for scenario_file in scenarios:
        try:
            with open(scenario_file, 'r') as f:
                data = json.load(f)
            print(f"    - {data.get('scenario_id', 'unknown')}: {data.get('title', 'N/A')}")
        except Exception as e:
            print(f"    ✗ Error loading {scenario_file.name}: {e}")
            return False

    return len(scenarios) > 0

if __name__ == "__main__":
    print("="*60)
    print("LongitudinalBench API Test")
    print("="*60)

    # Test 1: API keys
    if not test_api_keys():
        print("\n⚠️  No API keys configured. Please set up .env file.")
        exit(1)

    # Test 2: OpenRouter call
    if not test_openrouter_call():
        print("\n⚠️  OpenRouter API test failed. Check your API key.")
        exit(1)

    # Test 3: Scenario loading
    if not test_scenario_loading():
        print("\n⚠️  Scenario loading failed.")
        exit(1)

    print("\n" + "="*60)
    print("✓ All tests passed! Ready to run benchmark.")
    print("="*60)

    print("\nNext steps:")
    print("1. Run single scenario test:")
    print("   python -m src.runner --single-scenario tier1_crisis_detection --single-model openai/gpt-4o-mini")
    print("\n2. Run full benchmark on selected models:")
    print("   python -m src.runner --models openai/gpt-4o-mini anthropic/claude-3.7-sonnet")
    print()
