# Project Notes

## Repository overview
This repo maintains a longitudinal dataset of election official job postings scraped from electionline Weekly (2011–present). The pipeline runs weekly on Fridays, scraping new postings, extracting structured fields via Claude Haiku, and appending to the dataset.

## Key files
- `dataset.csv` — Main dataset (1,619 rows as of March 2026, 16 columns)
- `elw_scraper/process_listings.py` — Core pipeline: scraping, parsing, Claude API calls for feature extraction and classification
- `elw_scraper/add_new_pages.py` — Weekly update script
- `elw_scraper/scrape_full_descriptions.py` — Scrapes full job description text from linked URLs
- `job-descriptions/` — Full text files organized by year/date
- `analysis.ipynb` — Main analysis notebook
- `responsibilities_analysis.ipynb` — Responsibilities-focused analysis
- `make_responsibility_plots.py` — Script for generating responsibility visualizations

## Tech stack (current)
- Web scraping: Beautiful Soup
- Feature extraction & classification: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) via Anthropic Python SDK, using structured JSON output (`output_config` with `json_schema`)
- Data: pandas, CSV, Google Sheets (via gspread)
- NOTE: The README historically referenced scrapeghost and GPT-3.5. These have been replaced by Claude Haiku.

## Data quality notes (assessed March 2026)

### Stub descriptions (the `description` column)
- Available for all 1,619 rows — the most consistent signal across the full time series
- Average ~1,350 chars; range from 14 to 6,775 chars
- ~60-70% mention skill-related keywords (experience, knowledge, degree, etc.)
- Early years (2011-2013) have some very short/minimal stubs

### Full text files
- Available for 1,084/1,619 rows (67%)
- Coverage by era:
  - 2011-2014: 25-59% coverage, median file size 280-540 chars (many are just stubs re-scraped)
  - 2015-2017: 58-70% coverage, median 600-1,140 chars
  - 2018-2021: 48-82% coverage, median 3,500-5,200 chars (much richer)
  - 2022-2026: 72-100% coverage, median 5,800-8,900 chars
- ~121 full texts are error pages ("this job has moved", "page not found", etc.)
- The early full texts are often too short to contain detailed skill/qualification lists

### Year distribution
- 2011-2014: 40-54 postings/year (small samples)
- 2015-2018: 53-82 postings/year
- 2019-2026: 111-200 postings/year (much larger)
- 2026: only 14 so far (partial year)

### Other fields
- `salary_*`: ~28-29% missing
- `state`: ~9% missing
- `classification_experimental`: 100% populated but accuracy is described as "moderate"

## Planned analysis: Skills trend over time

### Goal
Track how the number of required skills in election official job postings has changed over time (2011–2025).

### Approach
1. **Data cleaning** — Filter out ~121 error-page full texts. Flag full texts <200 chars as unreliable. Create a "best available text" column (full text when substantive, else stub).

2. **Skill taxonomy** — Define structured categories grounded in actual posting content:
   - Election administration / ballot processing
   - Voter registration systems
   - Legal / regulatory compliance
   - Data management / analysis
   - IT / cybersecurity / election technology
   - Project management
   - Personnel management / supervision
   - Public communication / outreach
   - Bilingual / language skills
   - Budgeting / finance
   - GIS / mapping / redistricting
   - Formal qualifications (degrees, certifications)
   (Finalize after sampling ~30 postings across years)

3. **LLM-based skill extraction** — Use Claude Haiku (same pattern as existing `parse_and_classify_with_claude`) to extract skills from each posting against the taxonomy. Return structured JSON with skill categories and counts.

4. **Stub vs. full text comparison** — Run extraction on both stub and full text for the ~1,084 rows that have both. Quantify the undercount in stubs to decide whether stub-only trends are reliable.

5. **Trend analysis** — Mean/median skills per posting by year, overall and by category. Use stubs-only as consistent 2011-2025 baseline; overlay full-text trend for 2018+ where coverage is solid. Consider 2-3 year bins for early years (small n). Break out by job level using classification column.

6. **Visualization** — Time series, category heatmaps, stub-vs-full-text comparison. Match style of existing figures.

7. **Validation** — Manually spot-check ~50 extractions. Verify trend isn't an artifact of stub description length increasing over time.

### Key caveats
- Survivorship bias in full texts: early years have sparse, short full texts
- Small samples pre-2015 mean noisy year-over-year comparisons
- "Required" vs. "preferred" skills distinction may be hard to maintain consistently
- The dataset itself has grown over time (more postings per year), which could reflect real market growth or just better coverage by electionline
