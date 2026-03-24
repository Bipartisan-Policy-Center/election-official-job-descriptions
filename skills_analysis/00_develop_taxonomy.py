"""
00_develop_taxonomy.py
----------------------
Draws the stratified sample of job postings that was used to inductively
develop the skill taxonomy (skill_taxonomy.md).

This script does not produce an analysis output — it produces a reading list.
The taxonomy itself was developed by a human-AI team reading the sampled
postings and identifying recurring skill/competency patterns. See
skill_taxonomy.md for the resulting categories and methodology note.

SAMPLING DESIGN
---------------
We wanted the taxonomy to be grounded in actual posting content across the
full time range, not derived from recent postings alone. We stratified by:

  - Era: four periods of roughly equal span
      2013–2016  (early; small full-text coverage)
      2017–2019  (mid; growing coverage)
      2020–2022  (recent; rich coverage begins)
      2023–2025  (most recent; richest texts)

  - Job level: restricted to election_official and top_election_official
    (excluding not_election_official, which have different skill profiles)

  - Text quality: restricted to rich_full_text only, since marginal texts
    often lack the qualifications sections needed for taxonomy development

Within each era, we drew a small random sample (2–4 postings) using a fixed
random seed for reproducibility.

HOW TO REPLICATE
----------------
Run from repo root after running 01_classify_text_quality.py:
  python3 skills_analysis/00_develop_taxonomy.py

Prints the file paths of the sampled postings so you can read them.
The taxonomy was developed from the sample drawn on 2026-03-23.
"""

import os
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUALITY_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset_with_quality.csv")

# Stratification parameters
ERAS = [
    (2013, 2016, 2),
    (2017, 2019, 3),
    (2020, 2022, 3),
    (2023, 2025, 4),
]
TARGET_LEVELS = ["election_official", "top_election_official"]
TARGET_QUALITY = "rich_full_text"
RANDOM_SEED = 42


def main():
    df = pd.read_csv(QUALITY_CSV)

    eligible = df[
        (df["text_quality"] == TARGET_QUALITY) &
        (df["classification_experimental"].isin(TARGET_LEVELS))
    ].copy()

    samples = []
    for start, end, n in ERAS:
        era_df = eligible[(eligible["year"] >= start) & (eligible["year"] <= end)]
        n_actual = min(n, len(era_df))
        drawn = era_df.sample(n_actual, random_state=RANDOM_SEED + start)
        samples.append(drawn)
        print(f"Era {start}–{end}: drew {n_actual} of {len(era_df)} eligible postings")

    sample_df = pd.concat(samples).reset_index(drop=True)

    print(f"\nTotal sample: {len(sample_df)} postings\n")
    print(f"{'#':<4} {'Year':<6} {'Level':<25} {'Job Title':<45} {'Employer'}")
    print("-" * 120)
    for i, (_, row) in enumerate(sample_df.iterrows()):
        print(
            f"{i+1:<4} {row['year']:<6} {row['classification_experimental']:<25} "
            f"{str(row['job_title'])[:44]:<45} {row['employer']}"
        )

    print("\nFull text file paths:")
    for _, row in sample_df.iterrows():
        print(f"  {os.path.join(REPO_ROOT, row['full_text_file'])}")


if __name__ == "__main__":
    main()
