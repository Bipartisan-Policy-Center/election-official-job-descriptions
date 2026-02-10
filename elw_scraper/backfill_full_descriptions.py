#!/usr/bin/env python3
"""
Backfill script to scrape full descriptions for all existing jobs in dataset.csv.

This is a one-time script that:
1. Loads dataset.csv
2. Scrapes full descriptions for all jobs that don't have them yet
3. Saves progress incrementally (checkpoint system)
4. Updates dataset.csv with new columns
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime

sys.path.append('elw_scraper')
import scrape_full_descriptions

# Checkpoint file to track progress
CHECKPOINT_FILE = 'backfill_checkpoint.json'
BATCH_SIZE = 100  # Save progress every N rows


def load_checkpoint():
    """Load checkpoint from file if it exists."""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            return json.load(f)
    return {'last_completed_row': -1, 'start_time': datetime.now().isoformat()}


def save_checkpoint(row_index):
    """Save checkpoint to file."""
    checkpoint = {
        'last_completed_row': row_index,
        'last_update': datetime.now().isoformat()
    }
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(checkpoint, f, indent=2)


def main():
    print("Starting backfill of full job descriptions...")

    # Load existing dataset
    if not os.path.exists('dataset.csv'):
        print("Error: dataset.csv not found")
        sys.exit(1)

    df = pd.read_csv('dataset.csv')
    print(f"Loaded {len(df)} jobs from dataset.csv")

    # Load checkpoint
    checkpoint = load_checkpoint()
    start_row = checkpoint['last_completed_row'] + 1

    if start_row > 0:
        print(f"Resuming from row {start_row} (previous run completed {start_row} rows)")
    else:
        print("Starting fresh backfill")

    # Initialize new columns if they don't exist
    if 'full_text_preview' not in df.columns:
        df['full_text_preview'] = None
    if 'full_text_length' not in df.columns:
        df['full_text_length'] = None
    if 'full_text_scraped_date' not in df.columns:
        df['full_text_scraped_date'] = None
    if 'full_text_file' not in df.columns:
        df['full_text_file'] = None

    # Process in batches
    total_rows = len(df)
    rows_processed = 0
    rows_succeeded = 0
    rows_failed = 0

    # Track job numbers per date (reset counter for each date)
    date_counters = {}

    for idx in range(start_row, total_rows):
        row = df.iloc[idx]

        # Skip if already scraped
        if pd.notna(df.at[idx, 'full_text_preview']):
            print(f"Row {idx}: Already scraped, skipping")
            continue

        url = row['link']

        # Skip empty or invalid URLs
        if pd.isna(url) or url == '' or not str(url).startswith('http'):
            print(f"Row {idx}: Invalid URL, skipping")
            rows_processed += 1
            continue

        # Get job number for this date (1-based)
        date_key = f"{row['year']}-{row['date']}"
        if date_key not in date_counters:
            date_counters[date_key] = 1
        else:
            date_counters[date_key] += 1
        job_number = date_counters[date_key]

        # Scrape with retry logic
        text, error = scrape_full_descriptions.scrape_with_retry(url)

        if text is not None and len(text) > 0:
            # Save to file
            try:
                # Get job title for slug
                job_title = row.get('job_title', '')
                if pd.isna(job_title):
                    job_title = ''

                file_path = scrape_full_descriptions.save_full_description(
                    text, row['year'], row['date'], job_number, job_title
                )

                # Update dataframe
                df.at[idx, 'full_text_preview'] = text[:500]
                df.at[idx, 'full_text_length'] = len(text)
                df.at[idx, 'full_text_scraped_date'] = datetime.now().isoformat()
                df.at[idx, 'full_text_file'] = file_path

                rows_succeeded += 1
                print(f"Row {idx}: Success ({len(text)} chars)")
            except Exception as e:
                rows_failed += 1
                print(f"Row {idx}: Failed to save - {e}")
        else:
            rows_failed += 1
            error_msg = error if error else "Unknown error"
            print(f"Row {idx}: Failed to scrape - {error_msg}")

        rows_processed += 1

        # Save progress every BATCH_SIZE rows
        if rows_processed % BATCH_SIZE == 0:
            print(f"\n--- Checkpoint at row {idx} ---")
            print(f"Progress: {rows_processed}/{total_rows - start_row} rows processed")
            print(f"Success: {rows_succeeded}, Failed: {rows_failed}")
            print(f"Success rate: {rows_succeeded / rows_processed * 100:.1f}%")

            # Save checkpoint
            save_checkpoint(idx)

            # Save incremental CSV update
            df.to_csv('dataset.csv', index=False)
            print(f"Saved progress to dataset.csv\n")

    # Final save
    print(f"\n=== Backfill Complete ===")
    print(f"Total rows processed: {rows_processed}")
    print(f"Successful scrapes: {rows_succeeded}")
    print(f"Failed scrapes: {rows_failed}")
    print(f"Success rate: {rows_succeeded / rows_processed * 100:.1f}%")

    df.to_csv('dataset.csv', index=False)
    print("Final dataset.csv saved")

    # Clean up checkpoint file
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        print("Checkpoint file removed")


if __name__ == "__main__":
    main()
