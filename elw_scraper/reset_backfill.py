#!/usr/bin/env python3
"""
Helper script to reset backfill state completely.
Clears checkpoint, job description files, and CSV columns.
"""

import os
import shutil
import pandas as pd

def reset_backfill():
    """Reset all backfill state to start completely fresh."""

    print("Resetting backfill state...\n")

    # 1. Delete checkpoint file
    if os.path.exists('backfill_checkpoint.json'):
        os.remove('backfill_checkpoint.json')
        print("✓ Deleted checkpoint file")
    else:
        print("  (No checkpoint file found)")

    # 2. Delete job description files
    if os.path.exists('job-descriptions') and os.listdir('job-descriptions'):
        file_count = sum(len(files) for _, _, files in os.walk('job-descriptions'))
        shutil.rmtree('job-descriptions')
        os.makedirs('job-descriptions', exist_ok=True)
        print(f"✓ Deleted {file_count} job description files")
    else:
        print("  (No job description files found)")
        os.makedirs('job-descriptions', exist_ok=True)

    # 3. Clear full_text columns from CSV
    if os.path.exists('dataset.csv'):
        df = pd.read_csv('dataset.csv')

        full_text_cols = ['full_text_preview', 'full_text_length',
                          'full_text_scraped_date', 'full_text_file']

        cleared_cols = []
        for col in full_text_cols:
            if col in df.columns:
                df[col] = None
                cleared_cols.append(col)

        if cleared_cols:
            df.to_csv('dataset.csv', index=False)
            print(f"✓ Cleared {len(cleared_cols)} columns from dataset.csv: {', '.join(cleared_cols)}")
        else:
            print("  (No full_text columns found in CSV)")
    else:
        print("  (dataset.csv not found)")

    print("\n✓ Backfill reset complete!")
    print("You can now run: python elw_scraper/backfill_full_descriptions.py")


if __name__ == "__main__":
    reset_backfill()
