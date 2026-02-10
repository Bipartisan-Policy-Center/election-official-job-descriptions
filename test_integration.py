#!/usr/bin/env python3
"""
Integration test for the full pipeline using a sample of data.
"""

import sys
import os
import pandas as pd

sys.path.append('elw_scraper')

def test_full_pipeline():
    """Test the complete pipeline on a small sample."""
    import process_listings

    print("=" * 60)
    print("Integration Test: Full Pipeline")
    print("=" * 60)

    # Create sample data that mimics what job_descriptions() returns
    sample_data = pd.DataFrame([
        {
            'link': 'https://example.com',
            'description': 'County Elections Office seeks experienced Election Director for San Francisco County. Salary $120,000-$150,000/year. Must have 5+ years experience in election administration.',
            'date': '01-15',
            'year': 2024
        },
        {
            'link': 'https://www.governmentjobs.com/careers/wisconsin',
            'description': 'State of Wisconsin hiring Elections Specialist in Madison. $25-35/hour. Bachelor\'s degree required.',
            'date': '01-15',
            'year': 2024
        }
    ])

    print(f"\nSample data: {len(sample_data)} jobs")
    print(sample_data[['description']].to_string(index=False))

    # Test 1: Check if Claude API is configured
    if 'ANTHROPIC_API_KEY' not in os.environ:
        print("\n⚠ WARNING: ANTHROPIC_API_KEY not set")
        print("Skipping Claude API test")
        print("\nTo test Claude API integration:")
        print("  export ANTHROPIC_API_KEY='your-key-here'")
        print("  python test_integration.py")
        return False

    print("\n" + "-" * 60)
    print("Testing parse_and_classify_with_claude()...")
    print("-" * 60)

    try:
        result_df = process_listings.parse_and_classify_with_claude(sample_data)
        print("✓ Parse and classify completed")

        # Check if expected columns were added
        expected_cols = ['job_title', 'employer', 'state', 'salary_low_end',
                        'salary_high_end', 'pay_basis', 'classification_experimental']

        for col in expected_cols:
            if col in result_df.columns:
                print(f"  ✓ Column '{col}' added")
            else:
                print(f"  ✗ Column '{col}' missing!")
                return False

        # Display results
        print("\nExtracted data:")
        display_cols = ['job_title', 'state', 'salary_low_end', 'classification_experimental']
        print(result_df[display_cols].to_string(index=False))

    except Exception as e:
        print(f"✗ Parse and classify failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "-" * 60)
    print("Testing scrape_full_descriptions.scrape_new_jobs()...")
    print("-" * 60)

    try:
        import scrape_full_descriptions
        result_df = scrape_full_descriptions.scrape_new_jobs(result_df)
        print("✓ Scraping completed")

        # Check if expected columns were added
        scrape_cols = ['full_text_preview', 'full_text_length',
                      'full_text_scraped_date', 'full_text_file']

        for col in scrape_cols:
            if col in result_df.columns:
                print(f"  ✓ Column '{col}' added")
            else:
                print(f"  ✗ Column '{col}' missing!")
                return False

        # Display results
        print("\nScraping results:")
        for idx in result_df.index:
            row = result_df.loc[idx]
            if pd.notna(row['full_text_length']):
                print(f"  Row {idx}: ✓ {row['full_text_length']} chars scraped")
                print(f"    Preview: {row['full_text_preview'][:80]}...")
            else:
                print(f"  Row {idx}: ✗ Failed to scrape")

    except Exception as e:
        print(f"✗ Scraping failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "-" * 60)
    print("Testing handle_pay_basis()...")
    print("-" * 60)

    try:
        result_df = process_listings.handle_pay_basis(result_df)
        print("✓ Pay basis handling completed")

        if 'salary_mean' in result_df.columns:
            print(f"  ✓ Salary mean calculated")
            print(f"\nSalary data:")
            salary_cols = ['salary_low_end', 'salary_high_end', 'salary_mean', 'pay_basis']
            print(result_df[salary_cols].to_string(index=False))
        else:
            print(f"  ✗ salary_mean column missing!")
            return False

    except Exception as e:
        print(f"✗ Pay basis handling failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "-" * 60)
    print("Testing mark_duplicates()...")
    print("-" * 60)

    try:
        result_df = process_listings.mark_duplicates(result_df)
        print("✓ Duplicate marking completed")

        if 'is_duplicate_job' in result_df.columns:
            print(f"  ✓ is_duplicate_job column added")
            print(f"  Duplicates found: {result_df['is_duplicate_job'].sum()}")
        else:
            print(f"  ✗ is_duplicate_job column missing!")
            return False

    except Exception as e:
        print(f"✗ Duplicate marking failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 60)
    print("✓ Integration test passed!")
    print("=" * 60)

    # Show final dataframe structure
    print(f"\nFinal DataFrame shape: {result_df.shape}")
    print(f"Columns: {list(result_df.columns)}")

    return True


if __name__ == "__main__":
    success = test_full_pipeline()
    sys.exit(0 if success else 1)
