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

REPO_ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR    = os.path.dirname(os.path.abspath(__file__))
ORIG_CSV      = os.path.join(REPO_ROOT, "dataset.csv")
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


def fill_missing_metadata(df, orig_df):
    """
    For rows where job_title or employer is null after LLM extraction, fall
    back to the corresponding value from the original dataset.csv (which used
    an older model but was reliable for these two fields — it extracted from
    stubs that always have "Title, Employer – description" format).

    For state, fall back to regex on the stub description, converting full
    state names to 2-letter abbreviations. The original dataset used
    inconsistent formats ("California", "Washington, D.C.", "unknown") so we
    do NOT fall back to it for state.

    Only fills when the extracted value is null — never overwrites.
    A 'metadata_source' column records which rows were filled from each source.
    """
    import re

    STATE_ABBREVS = {
        'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
        'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
        'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
        'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
        'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
        'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
        'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
        'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
        'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
        'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
        'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
        'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
        'Wisconsin': 'WI', 'Wyoming': 'WY', 'District of Columbia': 'DC',
    }
    state_pattern = re.compile(
        r',\s*(' + '|'.join(re.escape(s) for s in STATE_ABBREVS) + r')\s*(?:,|\s|$)',
        re.IGNORECASE
    )

    # Mark source for all LLM-extracted rows
    df["metadata_source"] = "llm"

    filled_title = filled_employer = filled_state = 0
    for i, row in df.iterrows():
        orig_row = orig_df.iloc[i] if i < len(orig_df) else None

        # job_title: fall back to original dataset.csv value
        if pd.isna(row.get("job_title")) and orig_row is not None:
            val = orig_row.get("job_title")
            if pd.notna(val):
                df.at[i, "job_title"] = val
                df.at[i, "metadata_source"] = "orig_fallback"
                filled_title += 1

        # employer: fall back to original dataset.csv value
        if pd.isna(row.get("employer")) and orig_row is not None:
            val = orig_row.get("employer")
            if pd.notna(val):
                df.at[i, "employer"] = val
                if df.at[i, "metadata_source"] != "orig_fallback":
                    df.at[i, "metadata_source"] = "orig_fallback"
                filled_employer += 1

        # state: regex on stub (original format was too inconsistent to reuse)
        if pd.isna(row.get("state")):
            stub = str(row.get("description", "") or "")
            sm = state_pattern.search(stub[:500])
            if sm:
                name = sm.group(1)
                matched = next(
                    (k for k in STATE_ABBREVS if k.lower() == name.lower()), None
                )
                if matched:
                    df.at[i, "state"] = STATE_ABBREVS[matched]
                    filled_state += 1

    print(f"  Fallback filled: {filled_title} job_title (from orig), "
          f"{filled_employer} employer (from orig), {filled_state} state (from stub regex)")
    return df


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
    orig_df      = pd.read_csv(ORIG_CSV)
    quality_df   = pd.read_csv(QUALITY_CSV)
    extracted_df = pd.read_csv(EXTRACTED_CSV)

    print(f"Loaded {len(orig_df)} rows from {ORIG_CSV}")
    print(f"Loaded {len(quality_df)} rows from {QUALITY_CSV}")
    print(f"Loaded {len(extracted_df)} rows from {EXTRACTED_CSV}")

    # Keep only the raw columns from quality_df
    raw_cols_present = [c for c in RAW_COLS if c in quality_df.columns]
    raw_df = quality_df[raw_cols_present].copy()

    # Join on row_index (drop after merge, not before)
    merged = raw_df.merge(
        extracted_df,
        left_index=True,
        right_on="row_index",
        how="left"
    ).drop(columns=["row_index"], errors="ignore")

    print(f"Merged: {len(merged)} rows")

    # Fill null metadata fields: job_title/employer from original dataset,
    # state from stub regex (original state format was too inconsistent to reuse)
    print("\n=== Metadata fallback ===")
    merged = fill_missing_metadata(merged, orig_df)

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
