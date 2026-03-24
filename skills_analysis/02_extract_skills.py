"""
02_extract_skills.py
--------------------
Runs Claude Haiku over each posting to extract skills, reclassify jobs,
and recover additional structured fields. Bundles everything into a single
API call per row so the text is only read once.

WHAT IS EXTRACTED
-----------------
  Skill categories (required / preferred / mentioned), using the 12-code
  taxonomy defined in skill_taxonomy.md. Categories 1-12 only; formal
  qualifications are tracked separately.

  Election security flag — boolean, true only when posting uses explicit
  election-security language (not just general IT/cybersecurity).

  Formal qualifications — degree level and field, minimum years of
  experience, and certifications (required / preferred / substitutable).

  Job reclassification — revised classification using a more precise
  definition than the original classification_experimental column.
  Returns "borderline" when genuinely ambiguous.

  New fields (null unless explicitly stated in the posting):
    position_elected  — true if the role is an elected position
    full_time         — true if posting says full-time; false if part-time
    remote_hybrid     — "on_site" / "hybrid" / "remote"
    registered_voters — integer if jurisdiction size is mentioned in text

  Salary recovery — only attempted for rows where salary_mean is missing.
  Returns null if salary is not stated, rather than guessing.

NULL-FIRST PRINCIPLE
--------------------
The extraction prompt instructs the model to return null for any field it
cannot determine with confidence from the text. Pydantic enforces valid
values at the type level (e.g. Optional[Literal[...]] for nullable enums).
Downstream analyses should treat null as "not determinable" not "absent."

CACHING
-------
Raw API responses are saved to skills_analysis/api_cache/<row_index>.json
before any post-processing. If a cache file exists for a row, the API call
is skipped. This means:
  - Results are fully reproducible from the cached files
  - The script can be interrupted and resumed without re-spending API budget
  - To re-extract a specific row, delete its cache file and re-run

REPLICATION
-----------
Run from repo root after running 01_classify_text_quality.py:
  python3 skills_analysis/02_extract_skills.py

For a limited smoke test:
  python3 skills_analysis/02_extract_skills.py --limit 5

Requires: anthropic, pandas, tqdm (all in requirements.txt)
Input:    skills_analysis/dataset_with_quality.csv
Output:   skills_analysis/skills_extracted.csv
          skills_analysis/api_cache/<row_index>.json  (one per row)
"""

import argparse
import os
import time
import pandas as pd
import anthropic
from tqdm import tqdm
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.dirname(os.path.abspath(__file__))

# Load .env from repo root if ANTHROPIC_API_KEY isn't already in the environment.
_env_path = os.path.join(REPO_ROOT, ".env")
if "ANTHROPIC_API_KEY" not in os.environ and os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ[_k.strip()] = _v.strip()

INPUT_CSV  = os.path.join(SKILLS_DIR, "dataset_with_quality.csv")
OUTPUT_CSV = os.path.join(SKILLS_DIR, "skills_extracted.csv")
CACHE_DIR  = os.path.join(SKILLS_DIR, "api_cache")

MODEL          = "claude-haiku-4-5-20251001"
MAX_TOKENS     = 2048
MAX_TEXT_CHARS = 10_000   # cap input; most postings are under 8k
RETRY_WAIT     = 60       # seconds to wait after a rate-limit error
MAX_RETRIES    = 3

# ---------------------------------------------------------------------------
# Pydantic schema
# ---------------------------------------------------------------------------

SkillCode = Literal[
    "ops", "vr", "legal", "it_cyber", "data", "pm",
    "personnel", "budget", "comms", "intergovt", "gis", "bilingual"
]

class ExtractionResult(BaseModel):
    # Core structured fields — extracted fresh from best available text.
    # These replace the original fields in dataset.csv, which were produced
    # by an older model from stub text only.
    job_title:  Optional[str]   = None
    employer:   Optional[str]   = None
    state:      Optional[str]   = None  # two-letter abbrev preferred; null if not determinable
    salary_low_end:  Optional[float] = None
    salary_high_end: Optional[float] = None
    pay_basis: Optional[Literal[
        "yearly", "monthly", "biweekly", "semi-monthly", "hourly"
    ]] = None

    # Skills
    skill_categories_required:  List[SkillCode] = Field(default_factory=list)
    skill_categories_preferred: List[SkillCode] = Field(default_factory=list)
    skill_categories_mentioned: List[SkillCode] = Field(default_factory=list)
    election_security_explicit: bool = False

    # Formal qualifications
    degree_required: Optional[Literal[
        "high_school", "associate", "bachelor", "master", "doctorate"
    ]] = None
    degree_field:              Optional[str]   = None
    min_years_experience:      Optional[float] = None
    experience_can_substitute: Optional[bool]  = None
    certifications_required:     List[str] = Field(default_factory=list)
    certifications_preferred:    List[str] = Field(default_factory=list)
    certifications_substitutable: List[str] = Field(default_factory=list)

    # Job classification (revised)
    job_classification: Literal[
        "election_official", "top_election_official",
        "not_election_official", "borderline"
    ]
    classification_confidence: Literal["high", "low"]

    # Additional fields — null unless explicitly stated in the posting
    position_elected:  Optional[bool]  = None
    full_time:         Optional[bool]  = None
    remote_hybrid:     Optional[Literal["on_site", "hybrid", "remote"]] = None
    registered_voters: Optional[float] = None

    # Extraction metadata
    text_confidence:  Literal["high", "medium", "low"]

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator(
        "skill_categories_required", "skill_categories_preferred",
        "skill_categories_mentioned", "certifications_required",
        "certifications_preferred", "certifications_substitutable",
        mode="before",
    )
    @classmethod
    def coerce_null_to_empty_list(cls, v):
        """
        The model sometimes returns the JSON string "null" for empty list
        fields instead of []. Coerce it (and Python None) to [] so Pydantic
        validation doesn't fail on what is semantically an empty list.
        """
        if v is None or v == "null":
            return []
        return v

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a careful research assistant extracting structured data from election official job postings for an academic study.

CORE FIELDS:
  job_title  — The title of the position as stated in the posting
  employer   — The hiring organization (county, city, state agency, etc.)
  state      — Two-letter US state abbreviation (e.g. "VA", "CA"); null if not determinable
  salary_low_end / salary_high_end — Numeric salary values as stated; null if not mentioned
  pay_basis  — One of: yearly, monthly, biweekly, semi-monthly, hourly; null if not stated

SKILL TAXONOMY — use only these 12 codes:
  ops        Election operations & administration (ballots, equipment, poll workers, election day)
  vr         Voter registration systems (VR database, NVRA compliance, list maintenance)
  legal      Legal & regulatory compliance (election law, HAVA, state statutes, campaign finance)
  it_cyber   IT, cybersecurity & election technology (EMS, voting systems, network security)
  data       Data management & analysis (databases, reporting, statistical analysis, Excel)
  pm         Project management & logistics (scheduling, deadlines, risk management, contracts)
  personnel  Personnel management & supervision (hiring, training, supervising staff/poll workers)
  budget     Budget & financial management (budgeting, cost estimation, grants, procurement)
  comms      Public communication & outreach (media, public speaking, voter education, social media)
  intergovt  Intergovernmental & stakeholder coordination (state/federal agencies, associations)
  gis        GIS, mapping & redistricting (geographic systems, precinct boundaries)
  bilingual  Bilingual / language skills (any non-English language requirement or preference)

JOB CLASSIFICATION DEFINITIONS:
  election_official     — Works in a public elections office administering elections at the
                          local or state level. Includes elections managers, specialists,
                          clerks, registrar deputies, state board of elections staff, etc.
  top_election_official — Head of a local or state elections office with full administrative
                          authority. Examples: county clerk (when elections is primary role),
                          director of elections, registrar of voters, state elections director.
  not_election_official — Adjacent role not directly administering elections: federal oversight
                          (EAC staff, DOJ), nonprofit/advocacy (NASED, NASS policy roles),
                          election technology vendors, academic researchers, attorneys at
                          non-elections organizations.
  borderline            — Genuinely ambiguous; use when you cannot determine with confidence.

NULL-FIRST RULE — CRITICAL:
Return null for ANY field you cannot determine with confidence from the text.
Do not guess. Do not infer. If the posting does not explicitly state something,
return null. This applies especially to:
  - state (do not infer from employer name alone)
  - salary fields (only extract if a number appears in the text)
  - position_elected (only true if posting explicitly says "elected position")
  - full_time (only if explicitly stated; do not assume)
  - remote_hybrid (only if explicitly stated)
  - registered_voters (only if a number is stated in the text)
  - certifications (only list if mentioned by name)

IMPORTANT: For all array fields (skill_categories_*, certifications_*), return an
empty array [] when there are no items — never return null or the string "null"."""


def build_user_message(text):
    return f"Extract structured data from this job posting.\n\nJOB POSTING:\n{text[:MAX_TEXT_CHARS]}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_best_text(row):
    """Return full text if usable, else stub description."""
    if row.get("best_text_source") == "full_text":
        fpath_rel = row.get("full_text_file")
        if pd.notna(fpath_rel):
            fpath = os.path.join(REPO_ROOT, fpath_rel)
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", errors="replace") as f:
                        return f.read()
                except Exception:
                    pass
    return str(row.get("description", ""))


def call_api(client, text, retries=0):
    """Call Claude Haiku with tool use for structured JSON output.

    Uses tools/function-calling rather than client.messages.parse because
    parse() requires server-side grammar compilation, which times out on
    schemas as large as ExtractionResult. Tool use avoids that step entirely
    while still enforcing structured output; Pydantic validation runs locally
    after the response arrives.
    """
    schema = ExtractionResult.model_json_schema()

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[{
                "name": "extract_job_data",
                "description": "Extract structured fields from an election official job posting.",
                "input_schema": schema,
            }],
            tool_choice={"type": "tool", "name": "extract_job_data"},
            messages=[{"role": "user", "content": build_user_message(text)}],
        )

        for block in response.content:
            if block.type == "tool_use":
                return ExtractionResult.model_validate(block.input)

        raise ValueError("No tool_use block in response")

    except anthropic.RateLimitError:
        if retries < MAX_RETRIES:
            print(f"\n  Rate limit — waiting {RETRY_WAIT}s (retry {retries + 1}/{MAX_RETRIES})")
            time.sleep(RETRY_WAIT)
            return call_api(client, text, retries + 1)
        raise


def post_process(result: ExtractionResult) -> ExtractionResult:
    """
    Ensure skill_categories_mentioned is a superset of required + preferred.
    Pydantic already enforces valid skill codes, so this is the only
    logical consistency check needed.
    """
    mentioned = set(result.skill_categories_mentioned)
    required  = set(result.skill_categories_required)
    preferred = set(result.skill_categories_preferred)
    missing   = (required | preferred) - mentioned
    if missing:
        result.skill_categories_mentioned = list(mentioned | required | preferred)
    return result

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Process only the first N rows (useful for smoke testing)"
    )
    args = parser.parse_args()

    os.makedirs(CACHE_DIR, exist_ok=True)

    df = pd.read_csv(INPUT_CSV)
    print(f"Loaded {len(df)} rows from {INPUT_CSV}")
    if args.limit:
        print(f"  Limiting to first {args.limit} rows (--limit)")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    rows_to_process = df.iterrows()
    if args.limit:
        rows_to_process = ((i, r) for i, (_, r) in
                           zip(range(args.limit), df.iterrows()))

    results = []
    errors  = []

    for idx, row in tqdm(df.iterrows(), total=args.limit or len(df),
                         desc="Extracting skills", ncols=120):
        if args.limit and idx >= args.limit:
            break

        cache_path = os.path.join(CACHE_DIR, f"{idx}.json")

        # Use cached result if available
        if os.path.exists(cache_path):
            with open(cache_path) as f:
                result = ExtractionResult.model_validate_json(f.read())
            results.append({"row_index": idx, **result.model_dump()})
            continue

        text = get_best_text(row)

        try:
            result = call_api(client, text)
            result = post_process(result)

            # Cache immediately — raw Pydantic JSON
            with open(cache_path, "w") as f:
                f.write(result.model_dump_json())

            results.append({"row_index": idx, **result.model_dump()})

        except Exception as e:
            errors.append({"row_index": idx, "error": str(e)})
            tqdm.write(f"  ERROR row {idx}: {e}")
            continue

    # ------------------------------------------------------------------
    # Assemble output CSV
    # ------------------------------------------------------------------
    results_df = pd.DataFrame(results)

    # Flatten list columns to pipe-separated strings for CSV storage
    list_cols = [
        "skill_categories_required", "skill_categories_preferred",
        "skill_categories_mentioned", "certifications_required",
        "certifications_preferred", "certifications_substitutable"
    ]
    for col in list_cols:
        if col in results_df.columns:
            results_df[col] = results_df[col].apply(
                lambda x: "|".join(x) if isinstance(x, list) else x
            )

    results_df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nSaved {len(results_df)} rows -> {OUTPUT_CSV}")

    if errors:
        errors_df = pd.DataFrame(errors)
        errors_path = os.path.join(SKILLS_DIR, "extraction_errors.csv")
        errors_df.to_csv(errors_path, index=False)
        print(f"Saved {len(errors_df)} errors -> {errors_path}")

    if len(results_df):
        print("\n=== Classification distribution ===")
        print(results_df["job_classification"].value_counts().to_string())
        print("\n=== Text confidence ===")
        print(results_df["text_confidence"].value_counts().to_string())
        print(f"\n=== Salary extracted: {results_df['salary_low_end'].notna().sum()} rows ===")


if __name__ == "__main__":
    main()
