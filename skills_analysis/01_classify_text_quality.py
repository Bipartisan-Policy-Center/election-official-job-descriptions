"""
01_classify_text_quality.py
---------------------------
Classifies each row in dataset.csv by the quality of its associated full-text file,
and adds two new columns:

  text_quality     : one of {rich_full_text, marginal_full_text, junk_full_text, stub_only}
  best_text_source : one of {full_text, stub}

Outputs dataset_with_quality.csv (in this folder) and a review sample
text_quality_review_sample.csv for spot-checking borderline classifications.

DESIGN NOTES
------------
Three sequential checks determine whether a full-text file is junk:

  1. Known error strings — regex scan of the first 800 characters only.
     Checking only the top of the file is intentional: error messages appear
     at page-top, and we don't want to falsely flag legitimate postings that
     happen to mention "access denied" or "404" deep in HR/legal boilerplate.

  2. Length floor — files under 200 characters are junk regardless of content.

  3. Repetition check — if fewer than 50% of sentences (>20 chars) are unique,
     the file is probably UI boilerplate echoing itself (e.g., a careers landing
     page that repeated two marketing sentences verbatim).

Non-junk files are tiered by length:
  >= 3,000 chars  -> rich_full_text     (detailed job postings; good for extraction)
  500-2,999 chars -> marginal_full_text (may contain partial skill info)
  200-499 chars   -> junk_full_text     (too short to be meaningful)

The 3,000-char threshold was chosen empirically: files below this tend to be
partial scrapes (benefits sections, application instructions) without substantive
qualifications text. Files above it reliably contain duties and requirements sections.

REPLICATION
-----------
Run from the repo root:
  python3 skills_analysis/01_classify_text_quality.py

Requires: pandas (already in requirements.txt)
Input:    dataset.csv, job-descriptions/ folder
Output:   skills_analysis/dataset_with_quality.csv
          skills_analysis/text_quality_review_sample.csv
"""

import os
import re
import random
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_CSV = os.path.join(REPO_ROOT, "dataset.csv")
OUTPUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset_with_quality.csv")
REVIEW_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "text_quality_review_sample.csv")

# Minimum character length to be considered non-junk
MIN_LENGTH = 200

# Character length thresholds for tiering non-junk files
MARGINAL_THRESHOLD = 500   # 200–499 is still junk; 500–2999 is marginal
RICH_THRESHOLD = 3000      # 3000+ is rich

# Regex checked against first N characters of each file (not full file)
JUNK_SCAN_CHARS = 800

# Regex patterns that signal an error page or wrong-domain scrape
JUNK_PATTERNS = [
    r"page not found",
    r"this job has (moved|been filled|closed|expired|been removed)",
    r"job listing (has|is) (expired|no longer available|been removed)",
    r"no longer available",
    r"oops[!.]?\s+we'?re sorry",
    r"the page you (were looking for|requested) (could not|cannot) be found",
    r"\b404\b",
    r"access denied",
    r"application (session|has) expired",
    r"javascript (is|must be) enabled",
    r"please enable javascript",
    r"^careers\s*$",                     # file is literally just "Careers"
    r"^equal opportunity employer\.?\s*$",  # just EEO boilerplate
]
JUNK_RE = re.compile("|".join(JUNK_PATTERNS), re.IGNORECASE)

# Minimum unique-sentence ratio; below this = boilerplate mirror
MIN_UNIQUE_RATIO = 0.5
# Only apply repetition check when there are enough sentences to be meaningful
MIN_SENTENCES_FOR_REPETITION_CHECK = 4

# Review sample sizes — four groups so the reviewer can compare across tiers
REVIEW_N_RICH = 8         # baseline: what a "good" file looks like
REVIEW_N_MARGINAL = 10    # borderline: were these worth keeping?
REVIEW_N_JUNK = 15        # excluded: did we throw out anything real?
REVIEW_N_SHORT_STUB = 5   # stub-only: how much content is in a stub?
REVIEW_RANDOM_SEED = 42


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------

def classify_row(row, repo_root):
    """
    Returns (text_quality, file_content_or_None, junk_reason_or_None).

    Reads the file once and returns its content so callers can reuse it
    without re-reading, e.g. for building the best_text column.
    junk_reason is a short string explaining why a file was classified as junk,
    or None if it passed all checks.
    """
    if pd.isna(row.get("full_text_file")) or pd.isna(row.get("full_text_length")):
        return "stub_only", None, None

    fpath = os.path.join(repo_root, row["full_text_file"])
    if not os.path.exists(fpath):
        return "stub_only", None, None

    length = row["full_text_length"]

    try:
        with open(fpath, "r", errors="replace") as f:
            content = f.read()
    except Exception:
        return "stub_only", None, None

    # Check 1: known error strings (scan top of file only)
    m = JUNK_RE.search(content[:JUNK_SCAN_CHARS])
    if m:
        return "junk_full_text", content, f"error_string: '{m.group()}'"

    # Check 2: length floor
    if length < MIN_LENGTH:
        return "junk_full_text", content, f"too_short: {int(length)} chars"

    # Check 3: repetition (boilerplate mirror)
    sentences = [s.strip() for s in re.split(r"[.!?]\s+", content) if len(s.strip()) > 20]
    if len(sentences) >= MIN_SENTENCES_FOR_REPETITION_CHECK:
        unique_ratio = len(set(sentences)) / len(sentences)
        if unique_ratio < MIN_UNIQUE_RATIO:
            return "junk_full_text", content, f"repetition: {unique_ratio:.0%} unique sentences"

    # Tier by length
    if length >= RICH_THRESHOLD:
        return "rich_full_text", content, None
    elif length >= MARGINAL_THRESHOLD:
        return "marginal_full_text", content, None
    else:
        return "junk_full_text", content, f"too_short: {int(length)} chars"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    df = pd.read_csv(INPUT_CSV)
    print(f"Loaded {len(df)} rows from {INPUT_CSV}")

    qualities = []
    junk_reasons = []
    for _, row in df.iterrows():
        quality, _, reason = classify_row(row, REPO_ROOT)
        qualities.append(quality)
        junk_reasons.append(reason)

    df["text_quality"] = qualities
    df["junk_reason"] = junk_reasons
    df["best_text_source"] = df["text_quality"].apply(
        lambda q: "full_text" if q in ("rich_full_text", "marginal_full_text") else "stub"
    )

    # Summary
    print("\n=== Text quality distribution ===")
    print(df["text_quality"].value_counts().to_string())
    print("\n=== Best text source ===")
    print(df["best_text_source"].value_counts().to_string())

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nSaved annotated dataset -> {OUTPUT_CSV}")

    # ------------------------------------------------------------------
    # Build review sample for spot-checking
    #
    # Includes four groups so the reviewer can compare across quality tiers:
    #   - rich:     baseline of what a "good" file looks like
    #   - marginal: files on the borderline — were they worth keeping?
    #   - junk:     files we excluded — did we throw out anything real?
    #   - stub_only: rows with no full text — how much content is in the stub?
    #
    # Each row shows: the stub description, the full text (up to 2,000 chars),
    # the length, and — for junk — which rule triggered the classification.
    # ------------------------------------------------------------------
    rich_sample = df[df["text_quality"] == "rich_full_text"].sample(
        min(REVIEW_N_RICH, len(df[df["text_quality"] == "rich_full_text"])),
        random_state=REVIEW_RANDOM_SEED
    )
    junk_sample = df[df["text_quality"] == "junk_full_text"].sample(
        min(REVIEW_N_JUNK, len(df[df["text_quality"] == "junk_full_text"])),
        random_state=REVIEW_RANDOM_SEED
    )
    marginal_sample = df[df["text_quality"] == "marginal_full_text"].sample(
        min(REVIEW_N_MARGINAL, len(df[df["text_quality"] == "marginal_full_text"])),
        random_state=REVIEW_RANDOM_SEED
    )
    short_stub = df[
        (df["text_quality"] == "stub_only") & (df["description"].str.len() < 300)
    ].sample(
        min(REVIEW_N_SHORT_STUB, len(df[
            (df["text_quality"] == "stub_only") & (df["description"].str.len() < 300)
        ])),
        random_state=REVIEW_RANDOM_SEED
    )

    review_rows = []
    for _, row in pd.concat([rich_sample, marginal_sample, junk_sample, short_stub]).iterrows():
        fpath_rel = row.get("full_text_file")
        full_text = ""
        if not pd.isna(fpath_rel):
            fpath = os.path.join(REPO_ROOT, fpath_rel)
            if os.path.exists(fpath):
                with open(fpath, "r", errors="replace") as f:
                    full_text = f.read()[:2000]  # enough to judge quality
        review_rows.append({
            "text_quality_assigned": row["text_quality"],
            "junk_reason": row.get("junk_reason", ""),
            "year": row["year"],
            "job_title": row["job_title"],
            "employer": row["employer"],
            "full_text_length": row.get("full_text_length", ""),
            "stub_description": str(row["description"])[:400],
            "full_text": full_text,
            # Reviewer fills these in:
            "reviewer_verdict": "",   # correct / false_positive / false_negative
            "reviewer_notes": "",
        })

    review_df = pd.DataFrame(review_rows)
    review_df.to_csv(REVIEW_CSV, index=False)
    print(f"Saved review sample ({len(review_df)} rows) -> {REVIEW_CSV}")


if __name__ == "__main__":
    main()
