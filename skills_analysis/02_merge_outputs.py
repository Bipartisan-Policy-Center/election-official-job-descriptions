"""
02_merge_outputs.py
-------------------
Joins the raw dataset (dataset.csv) with the extraction results from
01_extract_all.py (skills_extracted.csv) to produce the analysis-ready
file: dataset_final.csv.

Raw columns kept from dataset.csv (fields that can't be re-extracted):
  year, date, description, link,
  full_text_file, full_text_length, full_text_scraped_date, is_duplicate_job

All structured fields (job_title, employer, state, salary, skills,
qualifications, classification, text_used, etc.) come from skills_extracted.csv,
extracted fresh by Claude Haiku in 01_extract_all.py.

SALARY ANNUALIZATION
--------------------
Converts non-annual salary values to yearly equivalents:
  hourly × 2080, monthly × 12, biweekly × 26, semi-monthly × 24

salary_mean is the average of low and high ends. If only one end is present,
both are set to that value.

METADATA FALLBACK
-----------------
If job_title or employer is null after LLM extraction, falls back to the
corresponding value from dataset.csv (which used an older model but was
reliable for these two fields — they extracted from stubs that always have
"Title, Employer — description" format).

REPLICATION
-----------
Run from repo root after 01_extract_all.py has completed:
  python3 skills_analysis/02_merge_outputs.py

Input:  dataset.csv
        skills_analysis/skills_extracted.csv
Output: skills_analysis/dataset_final.csv
"""

import os
import re
import pandas as pd

REPO_ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR    = os.path.dirname(os.path.abspath(__file__))
RAW_CSV       = os.path.join(REPO_ROOT, "dataset.csv")
EXTRACTED_CSV = os.path.join(SKILLS_DIR, "skills_extracted.csv")
OUTPUT_CSV    = os.path.join(SKILLS_DIR, "dataset_final.csv")

RAW_COLS = [
    "year", "date", "description", "link",
    "full_text_file", "full_text_length", "full_text_scraped_date", "is_duplicate_job",
    "classification_experimental",   # kept for comparison with new LLM classification
]

SALARY_MULTIPLIERS = {
    "monthly":      12,
    "biweekly":     26,
    "semi-monthly": 24,
    "hourly":       2080,
}

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
_state_re = re.compile(
    r',\s*(' + '|'.join(re.escape(s) for s in STATE_ABBREVS) + r')\s*(?:,|\s|$)',
    re.IGNORECASE
)


def fill_missing_metadata(df, raw_df):
    """Fall back to dataset.csv values for null job_title / employer."""
    filled_title = filled_employer = filled_state = 0
    for i, row in df.iterrows():
        orig = raw_df.iloc[i] if i < len(raw_df) else None

        if pd.isna(row.get("job_title")) and orig is not None and pd.notna(orig.get("job_title")):
            df.at[i, "job_title"] = orig["job_title"]
            filled_title += 1

        if pd.isna(row.get("employer")) and orig is not None and pd.notna(orig.get("employer")):
            df.at[i, "employer"] = orig["employer"]
            filled_employer += 1

        if pd.isna(row.get("state")):
            stub = str(row.get("description", "") or "")
            m = _state_re.search(stub[:500])
            if m:
                name = next((k for k in STATE_ABBREVS if k.lower() == m.group(1).lower()), None)
                if name:
                    df.at[i, "state"] = STATE_ABBREVS[name]
                    filled_state += 1

    print(f"  Fallback filled: {filled_title} job_title, "
          f"{filled_employer} employer, {filled_state} state (stub regex)")
    return df


def annualize_salary(df):
    for basis, mult in SALARY_MULTIPLIERS.items():
        mask = df["pay_basis"] == basis
        df.loc[mask, "salary_low_end"]  *= mult
        df.loc[mask, "salary_high_end"] *= mult

    low_only  = df["salary_low_end"].notna()  & df["salary_high_end"].isna()
    high_only = df["salary_high_end"].notna() & df["salary_low_end"].isna()
    df.loc[low_only,  "salary_high_end"] = df.loc[low_only,  "salary_low_end"]
    df.loc[high_only, "salary_low_end"]  = df.loc[high_only, "salary_high_end"]
    df["salary_mean"] = df[["salary_low_end", "salary_high_end"]].mean(axis=1)
    return df


def main():
    raw_df       = pd.read_csv(RAW_CSV)
    extracted_df = pd.read_csv(EXTRACTED_CSV)

    print(f"Loaded {len(raw_df)} rows from {RAW_CSV}")
    print(f"Loaded {len(extracted_df)} rows from {EXTRACTED_CSV}")

    raw_cols_present = [c for c in RAW_COLS if c in raw_df.columns]
    merged = raw_df[raw_cols_present].merge(
        extracted_df,
        left_index=True,
        right_on="row_index",
        how="left",
    ).drop(columns=["row_index"], errors="ignore")

    print(f"Merged: {len(merged)} rows")

    print("\n=== Metadata fallback ===")
    merged = fill_missing_metadata(merged, raw_df)

    merged = annualize_salary(merged)
    merged.to_csv(OUTPUT_CSV, index=False)
    print(f"\nSaved {len(merged)} rows → {OUTPUT_CSV}")

    print("\n=== Text used ===")
    if "text_used" in merged.columns:
        print(merged["text_used"].value_counts().to_string())

    print("\n=== Salary coverage ===")
    print(f"  salary_mean non-null: {merged['salary_mean'].notna().sum()} "
          f"({merged['salary_mean'].notna().mean():.0%})")

    print("\n=== Classification ===")
    if "job_classification" in merged.columns:
        print(merged["job_classification"].value_counts().to_string())

    print("\n=== State coverage ===")
    print(f"  state non-null: {merged['state'].notna().sum()} "
          f"({merged['state'].notna().mean():.0%})")


if __name__ == "__main__":
    main()
