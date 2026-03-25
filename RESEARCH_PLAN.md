# Research Plan: Skills & Professionalization in Election Official Job Postings

**Project:** Analysis of election official job descriptions (2011–2025)
**Purpose:** Paper on professionalization of election administration — tracking skill demands, taxonomy of required competencies, and trends over time
**Last updated:** 2026-03-24

---

## Data Overview

- **1,638 rows** in `dataset.csv`, spanning 2011–present
- **Stub descriptions** (`description` column): available for all rows, avg ~1,350 chars — consistent signal across full time series
- **Full text files** (`job-descriptions/` folder): 1,084 rows have associated files, highly variable quality by era:
  - 2011–2014: 25–59% coverage, median file 280–540 chars (many are just stubs re-scraped)
  - 2015–2017: 58–70% coverage, median 600–1,140 chars
  - 2018–2021: 48–82% coverage, median 3,500–5,200 chars (much richer)
  - 2022–2026: 72–100% coverage, median 5,800–8,900 chars
- **Text selection**: no heuristics — the extraction LLM itself decides whether to use the full text or stub for each row (see Phase 3)
- **Year distribution**: small samples 2011–2014 (40–54/yr), growing 2015–2018, larger 2019–2026 (111–200/yr); 2026 is partial

---

## Phase 1: Text Triage

**Status: ✅ Complete (integrated into Phase 3)**

Rather than a separate heuristic classification pass, text selection is handled by the same Claude Haiku API call that performs skill extraction. For each row, the model receives both the electionline stub and the scraped full text (if available) and sets `text_used = "full_text"` only when the full text clearly describes the same job AND adds meaningful detail. Otherwise it falls back to `"stub"`. This eliminates fragile structural heuristics that couldn't reliably distinguish, e.g., HR portals from actual job postings.

There is no separate `text_quality` column or `dataset_with_quality.csv`. The `text_used` column in `dataset_final.csv` is the output of this step.

---

## Phase 2: Skill Taxonomy Development

**Status: ✅ Complete**

12-category taxonomy finalized and implemented. See `skills_analysis/skill_taxonomy.md` for full definitions.

| Code | Category |
|---|---|
| `ops` | Election operations & administration |
| `vr` | Voter registration systems |
| `legal` | Legal / regulatory compliance |
| `it_cyber` | IT / cybersecurity / election technology |
| `data` | Data management / analysis |
| `pm` | Project management |
| `personnel` | Personnel management / supervision |
| `budget` | Budget & financial management |
| `comms` | Public communication / outreach |
| `intergovt` | Intergovernmental & stakeholder coordination |
| `gis` | GIS / mapping / redistricting |
| `bilingual` | Bilingual / language skills |

Skills are extracted with three levels of intensity: `required`, `preferred`, and `mentioned` (superset). `election_security_explicit` is a separate boolean flag.

---

## Phase 3: LLM Skill Extraction Pipeline

**Status: ✅ Complete** — extraction finished, `dataset_final.csv` produced

**Technical approach:** Single Claude Haiku call per row (model: `claude-haiku-4-5-20251001`). The model receives:
1. The electionline stub in `<electionline_stub>` tags (always reliable)
2. The scraped full text in `<scraped_full_text>` tags (or a note that none is available)

In one call, it (1) selects which text to use and (2) extracts all structured fields:

```
text_used, job_title, employer, state,
salary_low_end, salary_high_end, pay_basis,
skill_categories_required, skill_categories_preferred, skill_categories_mentioned,
election_security_explicit,
degree_required, degree_field, min_years_experience, experience_can_substitute,
certifications_required, certifications_preferred, certifications_substitutable,
job_classification, classification_confidence,
position_elected, full_time, remote_hybrid, registered_voters,
text_confidence
```

Results cached to `skills_analysis/api_cache_combined/<row_idx>.json`. Safe to interrupt and resume.

**Pipeline scripts** (run from repo root):
```bash
python3 skills_analysis/01_extract_all.py       # ~90 min; resumable
python3 skills_analysis/02_merge_outputs.py     # ~5 sec
python3 skills_analysis/03_build_validation_sample.py  # ~5 sec
# or: bash skills_analysis/run_pipeline.sh
```

**Cost:** ~$4–6 per full run at Haiku pricing.

---

## Phase 4: Human Validation

**Status: 🔄 Infrastructure complete — human review pending**

**Sample design (30 rows total, all three reviewers cover the same rows):**
- 25 stratified rows: year era × job classification × text source (full_text vs. stub)
- 5 edge cases: very short stubs, borderline classification, high skill count, full-text spot-check

**Review tool:** `skills_analysis/validation_review.html` — self-contained browser tool with all review data embedded. Open in any browser; no server required.

**Threshold:** If error rate >15%, revisit extraction prompt.

**Also validate:** Whether stub-only extractions are reliable for extending trends to 2011–2014.

**Deliverable:** Completed `validation_sample.csv` with reviewer verdicts

---

## Phase 5: Trend Analysis

**Status: ⏳ Pending**

**Core question:** Have more skills been demanded of election officials over time?

**Analyses:**
1. **Skills over time** — mean/median skill category count per posting by year; bin 2011–2014 into 2-year periods due to small n
2. **Category-level trends** — which skill types are growing fastest? (Expect IT/cybersecurity inflection ~2016–2018)
3. **By job level** — use `job_classification` (top_election_official / election_official / not_election_official)
4. **Stub vs. full-text calibration** — quantify undercount in stubs; determine if stub-only trend is reliable for early years
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

**Status: ⏳ Pending — Will investigating**

**Goal:** Contextualize election official skill trends relative to comparable public sector roles.

| Approach | Pros | Cons | Effort |
|---|---|---|---|
| Internal control: `not_election_official` rows in dataset | Free, same source | Only ~263 rows; selection bias | Low |
| O*NET occupation profiles | Structured, authoritative | Not time-series | Low |
| Cite existing lit (Moynihan, ICMA surveys) | Peer-reviewed baseline | Indirect comparison | Low |
| USA Jobs / state job board scrape | True apples-to-apples | Requires new data collection | Medium-high |

**Recommended approach:** Use internal `not_election_official` control for primary analysis; reference O*NET and existing public admin literature for external validity. USA Jobs scrape as fallback if reviewers push back.

---

## Timeline

| Phase | Status | Notes |
|---|---|---|
| 1. Text triage | ✅ Complete | Integrated into Phase 3 — no separate step |
| 2. Taxonomy | ✅ Complete | 12 codes; see `skill_taxonomy.md` |
| 3. LLM extraction | ✅ Complete | `dataset_final.csv` produced |
| 4. Validation | 🔄 In progress | Tool built; human review pending |
| 5. Trend analysis | ⏳ Pending | |
| 6. Control group | ⏳ Pending | Will investigating |

---

## Files

All analysis scripts and outputs live in `skills_analysis/`. Scripts are numbered sequentially; each script's docstring explains its design choices and how to run it.

| File | Description |
|---|---|
| `dataset.csv` | Main dataset (1,638 rows, 16 columns) — input, do not modify |
| `RESEARCH_PLAN.md` | This document |
| `skills_analysis/PIPELINE.md` | Technical pipeline documentation |
| `skills_analysis/skill_taxonomy.md` | Skill taxonomy with operational definitions |
| `skills_analysis/01_extract_all.py` | Combined text selection + extraction (single Haiku call per row) |
| `skills_analysis/02_merge_outputs.py` | Joins dataset.csv + skills_extracted.csv → dataset_final.csv |
| `skills_analysis/03_build_validation_sample.py` | Builds 60-row stratified sample for human review |
| `skills_analysis/run_pipeline.sh` | Runs all 3 steps end-to-end; `--fresh` flag clears cache |
| `skills_analysis/api_cache_combined/` | Per-row JSON cache (one file per row index) — do not delete unless re-running |
| `skills_analysis/skills_extracted.csv` | Output of 01_extract_all.py |
| `skills_analysis/dataset_final.csv` | Analysis-ready dataset (~35 columns); output of 02_merge_outputs.py |
| `skills_analysis/validation_sample.csv` | 60-row review sample; output of 03_build_validation_sample.py |
| `skills_analysis/validation_review.html` | Self-contained browser review tool |
