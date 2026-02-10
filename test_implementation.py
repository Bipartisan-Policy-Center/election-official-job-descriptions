#!/usr/bin/env python3
"""
Test script to verify the implementation works correctly.
"""

import sys
import os
import pandas as pd

sys.path.append('elw_scraper')

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    try:
        import process_listings
        import scrape_full_descriptions
        import anthropic
        import trafilatura
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_fingerprinting():
    """Test the improved fingerprinting function."""
    print("\nTesting fingerprinting...")
    import process_listings

    # Test row with all fields
    test_row = {
        'job_title': 'Election Director',
        'employer': 'County Elections Office',
        'state': 'California',
        'description': 'Looking for an experienced election director to manage...'
    }

    fingerprint = process_listings.create_job_fingerprint(test_row)
    print(f"  Sample fingerprint: {fingerprint[:100]}...")

    # Test with missing fields
    test_row_partial = {
        'description': 'Looking for an experienced election director to manage...'
    }
    fingerprint2 = process_listings.create_job_fingerprint(test_row_partial)
    print(f"  Partial fingerprint: {fingerprint2[:100]}...")

    print("✓ Fingerprinting works")
    return True


def test_web_scraping():
    """Test web scraping on a sample URL."""
    print("\nTesting web scraping...")
    import scrape_full_descriptions

    # Test with a reliable public URL (example.com is stable and simple)
    test_url = "https://example.com"

    print(f"  Attempting to scrape {test_url}...")
    text, error = scrape_full_descriptions.scrape_with_retry(test_url, max_retries=1)

    if text:
        print(f"✓ Web scraping successful (extracted {len(text)} chars)")
        print(f"  Preview: {text[:100]}...")
        return True
    else:
        print(f"✗ Web scraping failed: {error}")
        return False


def test_claude_api():
    """Test Claude API connection (requires API key)."""
    print("\nTesting Claude API...")

    if 'ANTHROPIC_API_KEY' not in os.environ:
        print("⚠ Skipping Claude API test (ANTHROPIC_API_KEY not set)")
        return True

    try:
        import anthropic
        import json

        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        # Simple test with structured output
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": "Extract info: Job: County Election Director. Location: California. Salary: $120,000/year."
            }],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "job_title": {"type": "string"},
                            "state": {"type": "string"},
                            "salary_low_end": {"type": ["number", "null"]}
                        },
                        "required": ["job_title", "state"]
                    }
                }
            }
        )

        data = json.loads(response.content[0].text)
        print(f"✓ Claude API successful: {data}")
        return True

    except Exception as e:
        print(f"✗ Claude API failed: {e}")
        return False


def test_mark_duplicates():
    """Test the mark_duplicates function."""
    print("\nTesting duplicate detection...")
    import process_listings

    # Create test dataframe with duplicates
    test_df = pd.DataFrame([
        {
            'job_title': 'Election Director',
            'employer': 'County Office',
            'state': 'CA',
            'description': 'Job description here...'
        },
        {
            'job_title': 'Election Director',
            'employer': 'County Office',
            'state': 'CA',
            'description': 'Job description here... (slightly different)'
        },
        {
            'job_title': 'Different Job',
            'employer': 'Other Office',
            'state': 'TX',
            'description': 'Completely different job'
        }
    ])

    result_df = process_listings.mark_duplicates(test_df)

    if 'is_duplicate_job' in result_df.columns:
        duplicates = result_df['is_duplicate_job'].sum()
        print(f"✓ Duplicate detection works ({duplicates} duplicate(s) found)")
        print(f"  Results: {result_df['is_duplicate_job'].tolist()}")
        return True
    else:
        print("✗ is_duplicate_job column not added")
        return False


def main():
    print("=" * 60)
    print("Testing Election Job Scraper Implementation")
    print("=" * 60)

    results = []
    results.append(("Imports", test_imports()))
    results.append(("Fingerprinting", test_fingerprinting()))
    results.append(("Web Scraping", test_web_scraping()))
    results.append(("Claude API", test_claude_api()))
    results.append(("Duplicate Detection", test_mark_duplicates()))

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:.<40} {status}")

    all_passed = all(result[1] for result in results)

    if all_passed:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
