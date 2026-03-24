"""
02b_merge_outputs.py
--------------------
Joins dataset_with_quality.csv (the raw scraped data + text quality flags)
with skills_extracted.csv (all structured fields extracted by 02_extract_skills.py)
to produce a single analysis-ready file: dataset_final.csv.

The columns kept from dataset.csv / dataset_with_quality.csv are the ones
that cannot be re-extracted from the posting text:
  year, date, description, link, full_text_file, full_text_length,
  full_text_scraped_date, is_duplicate_job, text_quality, best_text_source

All structured fields (job_title, employer, state, salary, classification,
skills, qualifications, etc.) come from skills_extracted.csv — extracted
fresh by Claude Haiku from the best available text for each row.

SALARY ANNUALIZATION
--------------------
Salary values from the extraction are as stated in the posting (e.g. $25/hour,
$4,500/month). This script converts them to annual equivalents using the same
multipliers as the original pipeline (process_listings.py):
  hourly × 2080, monthly × 12, biweekly × 26, semi-monthly × 24

salary_mean is computed as the average of low and high ends. If only one end
is present, both are set to that value.

REPLICATION
-----------
Run from repo root after 02_extract_skills.py has completed:
  python3 skills_analysis/02b_merge_outputs.py

Input:  skills_analysis/dataset_with_quality.csv
        skills_analysis/skills_extracted.csv
Output: skills_analysis/dataset_final.csv
"""

import os
import pandas as pd

SKILLS_DIR    = os.path.dirname(os.path.abspath(__file__))
QUALITY_CSV   = os.path.join(SKILLS_DIR, "dataset_with_quality.csv")
EXTRACTED_CSV = os.path.join(SKILLS_DIR, "skills_extracted.csv")
OUTPUT_CSV    = os.path.join(SKILLS_DIR, "dataset_final.csv")

# Columns to keep from the raw dataset (cannot be re-extracted from posting text)
RAW_COLS = [
    "year", "date", "description", "link",
    "full_text_file", "full_text_length", "full_text_scraped_date",
    "is_duplicate_job", "text_quality", "junk_reason", "best_text_source",
]

# Multipliers to annualize non-annual salary values
SALARY_MULTIPLIERS = {
    "monthly":      12,
    "biweekly":     26,
    "semi-monthly": 24,
    "hourly":       2080,
}


def annualize_salary(df):
    """Convert salary columns to annual equivalents based on pay_basis."""
    for basis, multiplier in SALARY_MULTIPLIERS.items():
        mask = df["pay_basis"] == basis
        df.loc[mask, "salary_low_end"]  = df.loc[mask, "salary_low_end"]  * multiplier
        df.loc[mask, "salary_high_end"] = df.loc[mask, "salary_high_end"] * multiplier

    # Fill one-sided ranges
    low_only  = df["salary_low_end"].notna()  & df["salary_high_end"].isna()
    high_only = df["salary_high_end"].notna() & df["salary_low_end"].isna()
    df.loc[low_only,  "salary_high_end"] = df.loc[low_only,  "salary_low_end"]
    df.loc[high_only, "salary_low_end"]  = df.loc[high_only, "salary_high_end"]

    df["salary_mean"] = df[["salary_low_end", "salary_high_end"]].mean(axis=1)
    return df


def main():
    quality_df   = pd.read_csv(QUALITY_CSV)
    extracted_df = pd.read_csv(EXTRACTED_CSV)

    print(f"Loaded {len(quality_df)} rows from {QUALITY_CSV}")
    print(f"Loaded {len(extracted_df)} rows from {EXTRACTED_CSV}")

    # Keep only the raw columns from quality_df
    raw_cols_present = [c for c in RAW_COLS if c in quality_df.columns]
    raw_df = quality_df[raw_cols_present].copy()

    # Join on row_index
    merged = raw_df.merge(
        extracted_df.drop(columns=["row_index"], errors="ignore"),
        left_index=True,
        right_on="row_index",
        how="left"
    ).drop(columns=["row_index"], errors="ignore")

    print(f"Merged: {len(merged)} rows")

    # Annualize salary
    merged = annualize_salary(merged)

    merged.to_csv(OUTPUT_CSV, index=False)
    print(f"\nSaved {len(merged)} rows -> {OUTPUT_CSV}")

    # Summary
    print("\n=== Salary coverage ===")
    print(f"  salary_mean non-null: {merged['salary_mean'].notna().sum()} "
          f"({merged['salary_mean'].notna().mean():.0%})")

    print("\n=== Classification (revised) ===")
    if "job_classification" in merged.columns:
        print(merged["job_classification"].value_counts().to_string())

    print("\n=== Text quality ===")
    print(merged["text_quality"].value_counts().to_string())

    print("\n=== State coverage ===")
    print(f"  state non-null: {merged['state'].notna().sum()} "
          f"({merged['state'].notna().mean():.0%})")


if __name__ == "__main__":
    main()
