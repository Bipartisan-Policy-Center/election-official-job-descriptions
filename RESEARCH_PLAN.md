# Research Plan: Skills & Professionalization in Election Official Job Postings

**Project:** Analysis of election official job descriptions (2011–2025)
**Purpose:** Paper on professionalization of election administration — tracking skill demands, taxonomy of required competencies, and trends over time
**Last updated:** 2026-03-23

---

## Data Overview

- **1,638 rows** in `dataset.csv`, spanning 2011–present
- **Stub descriptions** (`description` column): available for all rows, avg ~1,350 chars — consistent signal across full time series
- **Full text files** (`job-descriptions/` folder): 1,098 rows have associated files, but quality is highly variable:
  - ~303 files are effectively junk (<500 chars, error pages, UI boilerplate, wrong-site scrapes)
  - ~374 files are marginal (500–3,000 chars)
  - ~381 files are rich (3,000+ chars) — concentrated in 2019–2026
- **Year distribution**: small samples 2011–2014 (40–54/yr), growing 2015–2018, larger 2019–2026 (111–200/yr); 2026 is partial

---

## Phase 1: Text Triage & Quality Classification

**Goal:** Assign a `text_quality` label to each row and create a `best_text` column for downstream extraction.

**Quality categories:**
- `rich_full_text` — full text ≥3,000 chars, no junk signals
- `marginal_full_text` — full text 500–3,000 chars, potentially useful
- `junk_full_text` — full text exists but is garbage (error pages, UI chrome, wrong domain)
- `stub_only` — no full text file, or file is missing

**Junk detection heuristics:**
- Known error strings: "page not found", "this job has moved", "page not available", etc.
- Domain mismatch signals (e.g., BPC careers page, Tufts EEO boilerplate)
- Length threshold: <200 chars → always junk
- Low word diversity / repeated sentences (UI boilerplate pattern)

**Output:**
- `text_quality` column added to working dataset
- `best_text` column: use full text when `rich_full_text` or `marginal_full_text`, else stub
- Sample of ~30 borderline cases for Will to review before locking in rules

**Deliverable:** `dataset_with_quality.csv` + quality audit summary

---

## Phase 2: Skill Taxonomy Development

**Goal:** Define the structured skill categories to use for LLM extraction. Must be grounded in actual posting content, not assumed a priori.

**Process:**
1. Sample ~40 postings stratified across years (5 per era: 2011–14, 2015–17, 2018–20, 2021–23, 2024–25) and job levels
2. Read full texts carefully; note all skill/qualification types mentioned
3. Draft taxonomy, resolve key design decisions (see below)
4. Will reviews and approves taxonomy before extraction runs

**Draft taxonomy (to be refined in Phase 2):**

| Category | Description |
|---|---|
| Election administration | Ballot processing, poll worker management, canvassing, certification |
| Voter registration systems | Statewide VR database, NVRA compliance, list maintenance |
| Legal / regulatory compliance | Election law, HAVA, state statutes, public records |
| Data management / analysis | Database management, reporting, statistical analysis |
| IT / cybersecurity / election technology | Voting systems, election tech, network security, EMS |
| Project management | Planning, scheduling, multi-task coordination, deadline management |
| Personnel management | Hiring, supervision, training, HR |
| Public communication / outreach | Media relations, public speaking, community engagement |
| Bilingual / language skills | Any non-English language requirement |
| Budget / finance | Fiscal management, procurement, grants |
| GIS / mapping / redistricting | Geographic systems, precinct management |
| Formal qualifications | Degrees, certifications (CME, CERA), licensures |

**Key design decisions to resolve:**
- Track "required" vs. "preferred" separately, or merge?
- Count presence (binary) or intensity (# of mentions)?
- Should "formal qualifications" be a separate dimension from functional skills?
- Handle multi-role postings (e.g., "Clerk/Treasurer") how?

**Deliverable:** `skill_taxonomy.md` — approved taxonomy document with operational definitions

---

## Phase 3: LLM Skill Extraction Pipeline

**Goal:** Use Claude Haiku to extract structured skill data from each posting at scale.

**Technical approach:**
- Same pattern as existing `parse_and_classify_with_claude` in `process_listings.py`
- Model: `claude-haiku-4-5-20251001` with structured JSON output
- Input: `best_text` (or stub fallback)
- Output per row:
  ```json
  {
    "skill_categories": ["election_admin", "legal_compliance", ...],
    "skill_count": 4,
    "required_qualifications": ["bachelor's degree", "5 years experience"],
    "preferred_qualifications": ["CME certification"],
    "text_confidence": "high" | "medium" | "low"
  }
  ```
- Also run on stubs for the ~1,084 rows with both sources → stub vs. full-text calibration

**Cost estimate:** ~1,638 rows × ~2,000 tokens avg = ~3.3M tokens input; at Haiku pricing, well under $5 total

**Output:** `skills_extracted.csv` keyed on row ID, stored alongside main dataset

**Deliverable:** Extraction script + `skills_extracted.csv`

---

## Phase 4: Human Validation

**Goal:** Spot-check extraction quality before drawing conclusions.

**Sample design:**
- 60 rows total: 50 stratified sample (by year era, job level, text quality tier) + 10 edge cases (very short texts, unusual job types)
- For each: show original text alongside extracted skills
- Reviewer marks: ✓ correct / ↑ undercounted / ↓ overcounted / ✗ wrong categories

**Threshold:** If error rate >15%, revisit extraction prompt before full run

**Also validate:** Whether stub-only extractions are reliable enough to extend trends to 2011–2014

**Deliverable:** `validation_sample.csv` / Google Sheet for review

---

## Phase 5: Trend Analysis

**Core question:** Have more skills been demanded of election officials over time?

**Analyses:**
1. **Skills over time** — mean/median skill category count per posting by year; bin 2011–2014 into 2-year periods due to small n
2. **Category-level trends** — which skill types are growing fastest? (Expect IT/cybersecurity inflection ~2016–2018)
3. **By job level** — use `classification_experimental` (top official vs. deputy/staff vs. non-election)
4. **Stub vs. full-text calibration** — quantify undercount in stubs; determine if stub-only trend line is reliable for early years
5. **Salary correlations** — regression of `salary_mean` on skill categories, controlling for state, year, job level (~28% missing salary data)
6. **Has the job description itself changed?** — text similarity / vocabulary shift over time

**Key caveats to address in paper:**
- Survivorship bias in full texts: early years have sparse, short files
- Small samples 2011–2014 → use binned periods, wider confidence intervals
- Dataset growth over time may reflect electionline coverage, not market change
- "Required" vs. "preferred" distinction may be hard to maintain across eras

**Deliverable:** Updated `analysis.ipynb` with trend figures; new figures for paper

---

## Phase 6: Control Group

**Goal:** Contextualize election official skill trends relative to comparable public sector roles.

**Options (in order of effort):**

| Approach | Pros | Cons | Effort |
|---|---|---|---|
| Internal control: `not_election_official` rows in dataset | Free, same source | Only 263 rows; selection bias | Low |
| O*NET occupation profiles | Structured, authoritative | Not time-series | Low |
| Cite existing lit (Moynihan, ICMA surveys) | Peer-reviewed baseline | Indirect comparison | Low |
| USA Jobs / state job board scrape | True apples-to-apples | Requires new data collection | Medium-high |

**Recommended approach:** Use internal `not_election_official` control for primary analysis; reference O*NET and existing public admin literature for external validity. USA Jobs scrape as fallback if reviewers push back.

**Will is investigating control group options in parallel.**

---

## Timeline

| Phase | Status | Notes |
|---|---|---|
| 1. Text triage | 🔄 In progress | |
| 2. Taxonomy | ⏳ Pending | Requires Will's review |
| 3. LLM extraction | ⏳ Pending | Depends on Phase 2 |
| 4. Validation | ⏳ Pending | Requires Will's review |
| 5. Trend analysis | ⏳ Pending | |
| 6. Control group | ⏳ Pending | Will investigating |

---

## Files

All analysis scripts and outputs live in `skills_analysis/`. Scripts are numbered sequentially; each script's docstring explains its design choices and how to run it.

| File | Description |
|---|---|
| `dataset.csv` | Main dataset (1,638 rows, 16 columns) — input, do not modify |
| `RESEARCH_PLAN.md` | This document |
| `skills_analysis/01_classify_text_quality.py` | Classifies full-text files; outputs `dataset_with_quality.csv` |
| `skills_analysis/skill_taxonomy.md` | Skill taxonomy with operational definitions (Phase 2) |
| `skills_analysis/02_extract_skills.py` | LLM skill extraction pipeline; outputs `skills_extracted.csv` (Phase 3) |
| `skills_analysis/03_build_validation_sample.py` | Builds spot-check sample for human review (Phase 4) |
| `skills_analysis/04_analyze_trends.py` | Trend analysis and figures (Phase 5) |
| `skills_analysis/dataset_with_quality.csv` | Output of 01 |
| `skills_analysis/text_quality_review_sample.csv` | Output of 01 — 30 borderline cases for spot-checking |
| `skills_analysis/skills_extracted.csv` | Output of 02 (once run) |
| `skills_analysis/validation_sample.csv` | Output of 03 (once run) |
