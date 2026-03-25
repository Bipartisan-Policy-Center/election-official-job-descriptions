"""
03_build_validation_sample.py
------------------------------
Build the human validation sample: 30 rows selected to cover the key
dimensions — year era, job level, and text source (full_text vs stub) —
plus a set of edge cases.

Sample design (30 rows total):
  • 25 stratified rows across:
      - Year eras:  early (2011-2014), mid (2015-2018), grow (2019-2022), recent (2023-2025)
      - Job level:  top_election_official, election_official, not_election_official
      - Text used:  full_text, stub
    Allocated proportionally to strata size; minimum 1 per non-empty cell.

  • 5 edge-case rows:
      - 2 × very short stubs (bottom 10% by description length)
      - 1 × borderline or low-confidence job classification
      - 1 × unusually high skill count (top 5% — potential over-extraction)
      - 1 × full_text row where stub and full text may diverge (spot-check)

Output: validation_sample.csv — one row per sampled posting, with all metadata,
both text sources, and all extracted skill fields.
"""

import os
import random
import pandas as pd
import numpy as np

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

BASE      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL_CSV = os.path.join(BASE, "skills_analysis", "dataset_final.csv")
OUT_CSV   = os.path.join(BASE, "skills_analysis", "validation_sample.csv")

# ---------------------------------------------------------------------------
# Load dataset
# ---------------------------------------------------------------------------
df = pd.read_csv(FINAL_CSV)
df.index.name = "row_id"
df = df.reset_index()

# ---------------------------------------------------------------------------
# Load best_text for each row
# text_used = "full_text" → read from file; "stub" → use description column
# ---------------------------------------------------------------------------
def load_best_text(row):
    if str(row.get("text_used", "")).strip() == "full_text":
        fpath_rel = row.get("full_text_file")
        if pd.notna(fpath_rel):
            fpath = os.path.join(BASE, str(fpath_rel))
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    return f.read().strip()
            except FileNotFoundError:
                pass
    return str(row.get("description", "")).strip()

print("Loading best_text for all rows…")
df["best_text"] = df.apply(load_best_text, axis=1)

# ---------------------------------------------------------------------------
# Assign year era
# ---------------------------------------------------------------------------
def assign_era(year):
    if year <= 2014:   return "2011-2014"
    elif year <= 2018: return "2015-2018"
    elif year <= 2022: return "2019-2022"
    else:              return "2023-2025"

df["era"] = df["year"].apply(assign_era)

# Exclude partial 2026 year from stratified sample
df_pool = df[df["year"] <= 2025].copy()

# ---------------------------------------------------------------------------
# Compute skill count (number of unique categories mentioned)
# ---------------------------------------------------------------------------
def count_skills(row):
    cats = str(row.get("skill_categories_mentioned", "") or "")
    return len([c for c in cats.split("|") if c.strip()])

df_pool["skill_count"] = df_pool.apply(count_skills, axis=1)

# ---------------------------------------------------------------------------
# STRATIFIED SAMPLE (25 rows)
# ---------------------------------------------------------------------------
STRATA_N = 25

eras   = ["2011-2014", "2015-2018", "2019-2022", "2023-2025"]
levels = ["top_election_official", "election_official", "not_election_official"]
tiers  = ["full_text", "stub"]

strat_pool = df_pool[
    df_pool["era"].isin(eras) &
    df_pool["job_classification"].isin(levels) &
    df_pool["text_used"].isin(tiers)
].copy()

strata_counts = (
    strat_pool
    .groupby(["era", "job_classification", "text_used"])
    .size()
    .reset_index(name="n")
)
strata_counts = strata_counts[strata_counts["n"] > 0]
total_pool = strata_counts["n"].sum()

strata_counts["alloc"] = np.maximum(
    1, np.round(STRATA_N * strata_counts["n"] / total_pool).astype(int)
)

while strata_counts["alloc"].sum() > STRATA_N:
    idx = strata_counts[strata_counts["alloc"] > 1]["alloc"].idxmax()
    strata_counts.at[idx, "alloc"] -= 1
while strata_counts["alloc"].sum() < STRATA_N:
    idx = strata_counts["n"].idxmax()
    strata_counts.at[idx, "alloc"] += 1

strat_pool = strat_pool.set_index("row_id")
sampled_ids = set()
strat_rows = []

for _, st in strata_counts.iterrows():
    era, level, tier, n_alloc = st["era"], st["job_classification"], st["text_used"], st["alloc"]
    candidates = strat_pool[
        (strat_pool["era"] == era) &
        (strat_pool["job_classification"] == level) &
        (strat_pool["text_used"] == tier)
    ]
    candidates = candidates[~candidates.index.isin(sampled_ids)]
    k = min(int(n_alloc), len(candidates))
    if k == 0:
        continue
    chosen = candidates.sample(n=k, random_state=SEED).copy()
    chosen["sample_type"] = "stratified"
    chosen["edge_case_type"] = ""
    sampled_ids.update(chosen.index.tolist())
    strat_rows.append(chosen)

strat_df = pd.concat(strat_rows).reset_index()
print(f"Stratified sample: {len(strat_df)} rows")

# ---------------------------------------------------------------------------
# EDGE CASES (5 rows)
# ---------------------------------------------------------------------------
edge_rows = []

def add_edge(candidates, n, label, exclude_ids):
    candidates = candidates[~candidates["row_id"].isin(exclude_ids)]
    k = min(n, len(candidates))
    if k == 0:
        return pd.DataFrame()
    chosen = candidates.sample(n=k, random_state=SEED).copy()
    chosen["sample_type"] = "edge_case"
    chosen["edge_case_type"] = label
    return chosen

df_pool_ri = df_pool.reset_index(drop=True)

# 2 × very short stubs
short_thresh = df_pool_ri["description"].str.len().quantile(0.10)
e1 = add_edge(df_pool_ri[df_pool_ri["description"].str.len() <= short_thresh],
              2, "very_short_stub", sampled_ids)
sampled_ids.update(e1["row_id"].tolist())
edge_rows.append(e1)

# 1 × borderline or low-confidence classification
border_pool = df_pool_ri[df_pool_ri["job_classification"] == "borderline"]
if len(border_pool) < 1 and "classification_confidence" in df_pool_ri.columns:
    low_conf = df_pool_ri[df_pool_ri["classification_confidence"].astype(str) == "low"]
    border_pool = pd.concat([border_pool, low_conf]).drop_duplicates()
e2 = add_edge(border_pool, 1, "borderline_classification", sampled_ids)
sampled_ids.update(e2["row_id"].tolist())
edge_rows.append(e2)

# 1 × high skill count (top 5% — potential over-extraction)
high_thresh = df_pool_ri["skill_count"].quantile(0.95)
e3 = add_edge(df_pool_ri[df_pool_ri["skill_count"] >= high_thresh],
              1, "high_skill_count", sampled_ids)
sampled_ids.update(e3["row_id"].tolist())
edge_rows.append(e3)

# 1 × full_text row — spot-check that full text is genuinely better than stub
e4 = add_edge(df_pool_ri[df_pool_ri["text_used"] == "full_text"],
              1, "full_text_spot_check", sampled_ids)
sampled_ids.update(e4["row_id"].tolist())
edge_rows.append(e4)

edge_df = pd.concat([r for r in edge_rows if len(r) > 0]).reset_index(drop=True)
print(f"Edge cases: {len(edge_df)} rows")

# ---------------------------------------------------------------------------
# Combine and output
# ---------------------------------------------------------------------------
validation_df = pd.concat([strat_df, edge_df], ignore_index=True)
validation_df = validation_df.sort_values(["era", "year", "sample_type"]).reset_index(drop=True)
validation_df.insert(0, "review_id", range(1, len(validation_df) + 1))

validation_df["reviewer_verdict"] = ""
validation_df["reviewer_notes"]   = ""
validation_df["flagged_fields"]   = ""

out_cols = [
    "review_id", "row_id", "sample_type", "edge_case_type",
    "year", "era", "date", "job_title", "employer", "state",
    "job_classification", "classification_confidence",
    "position_elected", "full_time", "remote_hybrid", "registered_voters",
    "text_used", "text_confidence", "skill_count",
    "salary_low_end", "salary_high_end", "pay_basis",
    "description",
    "best_text",
    "skill_categories_required", "skill_categories_preferred", "skill_categories_mentioned",
    "election_security_explicit",
    "degree_required", "degree_field", "min_years_experience", "experience_can_substitute",
    "certifications_required", "certifications_preferred", "certifications_substitutable",
    "link",
    "reviewer_verdict", "reviewer_notes", "flagged_fields",
]
out_cols = [c for c in out_cols if c in validation_df.columns]
validation_df[out_cols].to_csv(OUT_CSV, index=False)

print(f"\nSaved {len(validation_df)} rows → {OUT_CSV}")
print("\nSample breakdown:")
print(validation_df.groupby(["sample_type", "era", "job_classification", "text_used"],
                             dropna=False).size().to_string())
