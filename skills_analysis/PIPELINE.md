# Skills Analysis Pipeline

Extracts structured skill, qualification, and job metadata from election official
job postings in `dataset.csv`, producing `dataset_final.csv` for trend analysis.

## Overview

```
dataset.csv  +  job-descriptions/
        │
        ▼
01_extract_all.py        — one Claude Haiku call per row:
        │                  (1) decides which text to use (stub vs. full text)
        │                  (2) extracts all structured fields
        ▼
skills_extracted.csv  +  api_cache_combined/<idx>.json
        │
        ▼
02_merge_outputs.py      — joins raw dataset + extracted fields → dataset_final.csv
        │
        ▼
dataset_final.csv        — analysis-ready, ~35 columns
        │
        ▼
03_build_validation_sample.py  — 30-row stratified human review sample
        │
        ▼
validation_sample.csv  +  validation_review.html
```

## Running the pipeline

```bash
cd /path/to/election-official-job-descriptions

# Step 1: extract everything (~90 min for 1,638 rows; fully resumable)
python3 skills_analysis/01_extract_all.py

# Step 2: merge into analysis-ready file (~5 sec)
python3 skills_analysis/02_merge_outputs.py

# Step 3: build validation sample (~5 sec)
python3 skills_analysis/03_build_validation_sample.py
```

Or all at once:
```bash
bash skills_analysis/run_pipeline.sh
```

To start completely fresh:
```bash
bash skills_analysis/run_pipeline.sh --fresh
```

Smoke test (10 rows):
```bash
python3 skills_analysis/01_extract_all.py --limit 10
```

## Scripts

### 01_extract_all.py
The core pipeline step. For each row, loads the electionline stub (always from
`description`) and the scraped full text (from `job-descriptions/` if it exists),
then makes a single Claude Haiku call that:

1. **Selects the text** — decides whether the scraped full text is the actual
   job posting or an unrelated page (portal, expired listing, homepage, etc.).
   Sets `text_used = "full_text"` or `"stub"` accordingly.

2. **Extracts all fields** from whichever text it chose:
   - Core metadata: `job_title`, `employer`, `state`
   - Salary: `salary_low_end`, `salary_high_end`, `pay_basis`
   - Skills (12-category taxonomy): required / preferred / mentioned
   - Election security flag
   - Qualifications: degree level/field, years of experience, certifications
   - Job classification: `election_official` / `top_election_official` /
     `not_election_official` / `borderline`
   - Additional fields: `position_elected`, `full_time`, `remote_hybrid`,
     `registered_voters`
   - Extraction confidence: `text_confidence`

Results cached to `api_cache_combined/<row_idx>.json`. Safe to interrupt and
resume — cached rows are skipped automatically.

**~$4–6 per full run (Claude Haiku pricing).**

### 02_merge_outputs.py
Joins `dataset.csv` (raw scraped data) with `skills_extracted.csv` (all
extracted fields). Columns kept from `dataset.csv`:

| Column | Notes |
|---|---|
| `year`, `date` | Time axis for trend analysis |
| `description` | Electionline stub (always available) |
| `link` | Original posting URL |
| `full_text_file` | Path to scraped full text |
| `full_text_length`, `full_text_scraped_date` | Provenance |
| `is_duplicate_job` | De-duplication flag |
| `classification_experimental` | Original classification for comparison |

Also annualizes salary values (hourly/monthly → yearly) and applies metadata
fallbacks (null `job_title`/`employer` filled from `dataset.csv` originals).

### 03_build_validation_sample.py
Builds a stratified 30-row sample (25 stratified by era × job level × text
source, plus 5 edge cases) for human validation of extraction quality. Output
feeds `validation_review.html`, a self-contained browser-based review tool.

## Skill taxonomy (12 codes)

| Code | Category |
|---|---|
| `ops` | Election operations & administration |
| `vr` | Voter registration systems |
| `legal` | Legal / regulatory compliance |
| `it_cyber` | IT / cybersecurity / election technology |
| `data` | Data management / analysis |
| `pm` | Project management |
| `personnel` | Personnel management / supervision |
| `budget` | Budgeting / finance |
| `comms` | Public communication / outreach |
| `intergovt` | Intergovernmental relations |
| `gis` | GIS / mapping / redistricting |
| `bilingual` | Bilingual / language skills |

See `skill_taxonomy.md` for full definitions and design decisions.

## Cache

`api_cache_combined/` — one JSON file per row (`<row_idx>.json`), storing the
raw Pydantic-validated extraction result. Delete a file and re-run to
re-extract that row. Delete the whole directory to start fresh.
