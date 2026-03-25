"""
02c_compare_datasets.py
-----------------------
Compares the new dataset_final.csv against the original dataset.csv to
validate that the Claude Haiku re-extraction improves or at least matches
coverage on structured fields.

The comparison covers:
  1. Row counts (overall and by year)
  2. Field coverage — % non-null for columns that exist in both datasets
  3. Salary coverage and distribution (mean, median, by year)
  4. Classification: old classification_experimental vs new job_classification,
     including a cross-tab showing where they agree / disagree
  5. State coverage
  6. New fields not present in the original (skills, qualifications, etc.)

REPLICATION
-----------
Run from repo root after 02_merge_outputs.py has completed:
  python3 skills_analysis/02c_compare_datasets.py

Input:  dataset.csv                      (original, at repo root)
        skills_analysis/dataset_final.csv (new)
Output: printed summary; no files written
"""

import os
import pandas as pd

REPO_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.dirname(os.path.abspath(__file__))

ORIG_CSV  = os.path.join(REPO_ROOT, "dataset.csv")
FINAL_CSV = os.path.join(SKILLS_DIR, "dataset_final.csv")

# Fields that have rough equivalents in both datasets
FIELD_MAP = {
    # new name          : old name
    "job_title"         : "job_title",
    "employer"          : "employer",
    "state"             : "state",
    "salary_mean"       : "salary_mean",
    "salary_low_end"    : "salary_low",
    "salary_high_end"   : "salary_high",
    "job_classification": "classification_experimental",
}

# Both old and new classification columns use the same underscore-separated
# values (election_official, top_election_official, not_election_official).
# No mapping needed — compare directly.


def coverage(series):
    """Return (n_nonnull, pct_nonnull) for a Series."""
    n = series.notna().sum()
    return n, n / len(series)


def sep(title=""):
    width = 60
    if title:
        print(f"\n{'─' * 4} {title} {'─' * max(0, width - len(title) - 6)}")
    else:
        print("─" * width)


def main():
    orig  = pd.read_csv(ORIG_CSV)
    final = pd.read_csv(FINAL_CSV)

    # ------------------------------------------------------------------ #
    # 1. Row counts
    # ------------------------------------------------------------------ #
    sep("ROW COUNTS")
    print(f"  Original dataset.csv : {len(orig):,} rows")
    print(f"  New dataset_final.csv: {len(final):,} rows")

    if "year" in orig.columns and "year" in final.columns:
        year_orig  = orig["year"].value_counts().sort_index()
        year_final = final["year"].value_counts().sort_index()
        ydf = pd.DataFrame({"original": year_orig, "final": year_final}).fillna(0).astype(int)
        ydf["diff"] = ydf["final"] - ydf["original"]
        print("\n  Rows per year (original vs final):")
        print(ydf.to_string(header=True))

    # ------------------------------------------------------------------ #
    # 2. Field coverage
    # ------------------------------------------------------------------ #
    sep("FIELD COVERAGE (% non-null)")
    print(f"  {'Field':<30} {'Original':>10} {'New':>10} {'Change':>10}")
    print(f"  {'─'*30} {'─'*10} {'─'*10} {'─'*10}")
    for new_col, old_col in FIELD_MAP.items():
        if new_col not in final.columns:
            continue
        n_new, pct_new = coverage(final[new_col])
        if old_col in orig.columns:
            n_old, pct_old = coverage(orig[old_col])
            change = pct_new - pct_old
            print(f"  {new_col:<30} {pct_old:>9.1%} {pct_new:>9.1%} {change:>+9.1%}")
        else:
            print(f"  {new_col:<30} {'(new)':>10} {pct_new:>9.1%} {'':>10}")

    # ------------------------------------------------------------------ #
    # 3. Salary comparison
    # ------------------------------------------------------------------ #
    sep("SALARY (annualized, non-null rows only)")
    for label, df in [("Original", orig), ("New", final)]:
        col = "salary_mean"
        if col in df.columns:
            s = df[col].dropna()
            print(f"  {label}: n={len(s):,}  "
                  f"median=${s.median():,.0f}  "
                  f"mean=${s.mean():,.0f}  "
                  f"range=${s.min():,.0f}–${s.max():,.0f}")

    if "year" in final.columns and "salary_mean" in final.columns:
        print("\n  Median salary_mean by year (new dataset):")
        by_year = (final.groupby("year")["salary_mean"]
                   .agg(["median", "count"])
                   .rename(columns={"median": "median_salary", "count": "n_with_salary"}))
        print(by_year.to_string())

    # ------------------------------------------------------------------ #
    # 4. Classification comparison
    # ------------------------------------------------------------------ #
    sep("CLASSIFICATION")
    print("  New job_classification distribution:")
    if "job_classification" in final.columns:
        print(final["job_classification"].value_counts().to_string())
        print(f"\n  classification_confidence breakdown:")
        if "classification_confidence" in final.columns:
            print(final["classification_confidence"].value_counts().to_string())

    if "classification_experimental" in orig.columns and "job_classification" in final.columns:
        # Both columns use the same labels; compare directly.
        # Exclude 'borderline' from the new column (not a valid old label).
        both = pd.DataFrame({
            "old": orig["classification_experimental"],
            "new": final["job_classification"],
        }).dropna(subset=["old"])
        comparable = both[both["new"] != "borderline"]
        agree = (comparable["old"] == comparable["new"]).sum()
        print(f"\n  Agreement (excluding borderline): "
              f"{agree:,}/{len(comparable):,} ({agree/len(comparable):.1%})")

        print("\n  Cross-tab old (rows) vs new (cols):")
        xtab = pd.crosstab(both["old"], both["new"], margins=True)
        print(xtab.to_string())

    # ------------------------------------------------------------------ #
    # 5. State coverage
    # ------------------------------------------------------------------ #
    sep("STATE COVERAGE")
    for label, df in [("Original", orig), ("New", final)]:
        if "state" in df.columns:
            n, pct = coverage(df["state"])
            print(f"  {label}: {n:,}/{len(df):,} ({pct:.1%}) non-null")

    # ------------------------------------------------------------------ #
    # 6. New fields in dataset_final.csv
    # ------------------------------------------------------------------ #
    sep("NEW FIELDS (not in original)")
    new_only = [c for c in final.columns if c not in orig.columns]
    print(f"  {len(new_only)} new columns: {', '.join(new_only)}")

    skill_cols = [c for c in final.columns if c.startswith("skill_categories_")]
    if skill_cols:
        print("\n  Skill extraction coverage (% rows with ≥1 skill):")
        for col in skill_cols:
            nonempty = final[col].dropna().astype(str).str.len().gt(0).sum()
            print(f"    {col:<40} {nonempty:>5,} ({nonempty/len(final):.1%})")

    for col in ["degree_required", "min_years_experience", "full_time",
                "position_elected", "remote_hybrid"]:
        if col in final.columns:
            n, pct = coverage(final[col])
            print(f"  {col}: {n:,} non-null ({pct:.1%})")


if __name__ == "__main__":
    main()
