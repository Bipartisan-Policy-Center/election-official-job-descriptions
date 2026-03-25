"""
01_extract_all.py
-----------------
Single-step pipeline: for each job posting, pass the electionline stub AND
the scraped full text (when available) to Claude Haiku in one call. The model
decides which text is the actual job posting, then extracts all structured
fields — skills, salary, classification, qualifications, and metadata.

WHY ONE STEP
------------
Earlier versions used a two-stage approach: structural heuristics to decide
which text to use, then a separate extraction call. That was fragile — wrong
pages often passed the heuristics. This version delegates the text-selection
judgment to the same LLM that does extraction, so the choice is informed by
actual content rather than length or keyword rules.

TEXT SELECTION LOGIC (done by the model)
-----------------------------------------
The model receives:
  - ELECTIONLINE STUB: always a reliable short summary written by electionline
    Weekly editors. Used as the authoritative description.
  - SCRAPED FULL TEXT: the text from the linked URL — may be the actual posting
    or an unrelated page (expired listing, portal homepage, benefits page, etc.)
  - If no full text exists, the model extracts from the stub only.

The model sets text_used = "full_text" only when the full text clearly
describes the same job AND adds meaningful detail. Otherwise: "stub".

CACHING
-------
Each row's result is cached to api_cache_combined/<row_index>.json immediately
after the API call. Re-running is safe — cached rows are skipped. To re-extract
a specific row, delete its cache file.

REPLICATION
-----------
Run from repo root:
  python3 skills_analysis/01_extract_all.py

Smoke test (first 10 rows):
  python3 skills_analysis/01_extract_all.py --limit 10

Requires: anthropic, httpx, pandas, tqdm, pydantic
Input:    dataset.csv, job-descriptions/ (full text files)
Output:   skills_analysis/skills_extracted.csv
          skills_analysis/api_cache_combined/<row_index>.json
"""

import argparse
import json
import os
import time

import anthropic
import httpx
import pandas as pd
from tqdm import tqdm
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.dirname(os.path.abspath(__file__))

# Load .env if ANTHROPIC_API_KEY isn't already set (or is empty).
_env_path = os.path.join(REPO_ROOT, ".env")
if not os.environ.get("ANTHROPIC_API_KEY") and os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ[_k.strip()] = _v.strip()

INPUT_CSV  = os.path.join(REPO_ROOT, "dataset.csv")
OUTPUT_CSV = os.path.join(SKILLS_DIR, "skills_extracted.csv")
CACHE_DIR  = os.path.join(SKILLS_DIR, "api_cache_combined")

MODEL       = "claude-haiku-4-5-20251001"
MAX_TOKENS  = 2048
RETRY_WAIT  = 60
MAX_RETRIES = 3

STUB_MAX_CHARS     = 3_000   # stubs are usually <2k; cap generously
FULL_TEXT_MAX_CHARS = 8_000  # most rich postings are under 8k

# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

SkillCode = Literal[
    "ops", "vr", "legal", "it_cyber", "data", "pm",
    "personnel", "budget", "comms", "intergovt", "gis", "bilingual"
]

class ExtractionResult(BaseModel):
    # Text selection — which source the model used for extraction
    text_used: Literal["stub", "full_text"]

    # Core structured fields
    job_title:       Optional[str]   = None
    employer:        Optional[str]   = None
    state:           Optional[str]   = None
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
    degree_field:               Optional[str]   = None
    min_years_experience:       Optional[float] = None
    experience_can_substitute:  Optional[bool]  = None
    certifications_required:      List[str] = Field(default_factory=list)
    certifications_preferred:     List[str] = Field(default_factory=list)
    certifications_substitutable: List[str] = Field(default_factory=list)

    # Job classification
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
    text_confidence: Literal["high", "medium", "low"]

    @field_validator(
        "certifications_required",
        "certifications_preferred",
        "certifications_substitutable",
        mode="before",
    )
    @classmethod
    def coerce_null_to_empty_list(cls, v):
        if v is None or v == "null":
            return []
        return v

    @field_validator(
        "skill_categories_required",
        "skill_categories_preferred",
        "skill_categories_mentioned",
        mode="before",
    )
    @classmethod
    def coerce_skill_codes(cls, v):
        """Coerce null to [] and silently drop any unrecognized skill codes.
        The model occasionally returns free-text descriptions (e.g. 'records
        management') instead of valid codes. Dropping them is preferable to
        failing the whole row — the other skills are still valid.
        """
        if v is None or v == "null":
            return []
        valid = {
            "ops", "vr", "legal", "it_cyber", "data", "pm",
            "personnel", "budget", "comms", "intergovt", "gis", "bilingual",
        }
        if isinstance(v, list):
            return [x for x in v if x in valid]
        return v


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a careful research assistant extracting structured data from election \
official job postings for an academic study.

You will receive two texts for each posting:
  1. ELECTIONLINE STUB — a short summary written by electionline Weekly editors.
     This is always reliable and describes the actual job.
  2. SCRAPED FULL TEXT — the text scraped from the linked URL. This may be the
     actual job posting with full details, or it may be an unrelated page
     (expired listing, HR portal, org homepage, benefits page, etc.).

YOUR FIRST TASK — decide which text to use:
  - Set text_used = "full_text" if the scraped text clearly describes the same
    job as the stub AND adds meaningful detail (duties, qualifications, salary).
  - Set text_used = "stub" in all other cases: if the full text is unrelated,
    generic, mostly boilerplate, or adds nothing beyond the stub.

YOUR SECOND TASK — extract all fields from whichever text you chose. You may
supplement from the other text if a field (e.g. salary) only appears there.

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

JOB CLASSIFICATION:
  election_official     — Works in a public elections office administering elections.
  top_election_official — Head of a local/state elections office with full authority.
                          (county clerk when elections is primary role, director of
                          elections, registrar of voters, state elections director)
  not_election_official — Adjacent role: federal oversight (EAC), nonprofit/advocacy,
                          election tech vendor, academic researcher, non-elections attorney.
  borderline            — Genuinely ambiguous.

NULL-FIRST RULE — CRITICAL:
Return null for ANY field you cannot determine with confidence from the text.
Do not guess or infer. This applies especially to:
  - state (do not infer from employer name alone)
  - salary fields (only if a number appears in the text)
  - position_elected (only if explicitly stated)
  - full_time (only if explicitly stated)
  - remote_hybrid (only if explicitly stated)
  - registered_voters (only if a number is stated)
  - certifications (only list if mentioned by name)

For all array fields, return [] when empty — never null."""


def build_user_message(stub: str, full_text: Optional[str]) -> str:
    stub_section = f"<electionline_stub>\n{stub[:STUB_MAX_CHARS]}\n</electionline_stub>"

    if full_text:
        ft_section = (
            f"<scraped_full_text>\n{full_text[:FULL_TEXT_MAX_CHARS]}\n</scraped_full_text>"
        )
    else:
        ft_section = (
            "<scraped_full_text>NO FULL TEXT AVAILABLE — "
            "extract from the stub only. Set text_used = \"stub\".</scraped_full_text>"
        )

    return (
        "Extract structured data from this job posting.\n\n"
        f"{stub_section}\n\n{ft_section}"
    )


# ---------------------------------------------------------------------------
# Text loading
# ---------------------------------------------------------------------------

def load_full_text(row) -> Optional[str]:
    """Try to read the scraped full text file. Returns None if unavailable."""
    fpath_rel = row.get("full_text_file")
    if pd.isna(fpath_rel):
        return None
    fpath = os.path.join(REPO_ROOT, str(fpath_rel))
    if not os.path.exists(fpath):
        return None
    try:
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip() or None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def call_api(client, stub: str, full_text: Optional[str], retries: int = 0) -> ExtractionResult:
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
            messages=[{"role": "user", "content": build_user_message(stub, full_text)}],
        )
        for block in response.content:
            if block.type == "tool_use":
                return ExtractionResult.model_validate(block.input)
        raise ValueError("No tool_use block in response")

    except anthropic.RateLimitError:
        if retries < MAX_RETRIES:
            tqdm.write(f"  Rate limit — waiting {RETRY_WAIT}s (retry {retries+1}/{MAX_RETRIES})")
            time.sleep(RETRY_WAIT)
            return call_api(client, stub, full_text, retries + 1)
        raise


def post_process(result: ExtractionResult) -> ExtractionResult:
    """Ensure skill_categories_mentioned is a superset of required + preferred."""
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
    parser = argparse.ArgumentParser(
        description="Extract skills and metadata from election job postings (combined text-selection + extraction)."
    )
    parser.add_argument("--limit", type=int, default=None,
                        help="Process only the first N rows (smoke test)")
    args = parser.parse_args()

    os.makedirs(CACHE_DIR, exist_ok=True)

    df = pd.read_csv(INPUT_CSV)
    print(f"Loaded {len(df)} rows from {INPUT_CSV}")
    if args.limit:
        df = df.head(args.limit)
        print(f"  Limiting to first {args.limit} rows (--limit)")

    _http = httpx.Client(verify=False)
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        http_client=_http,
    )

    results = []
    errors  = []

    for idx, row in tqdm(df.iterrows(), total=len(df),
                         desc="Extracting", ncols=100):
        cache_path = os.path.join(CACHE_DIR, f"{idx}.json")

        if os.path.exists(cache_path):
            with open(cache_path) as f:
                result = ExtractionResult.model_validate_json(f.read())
            results.append({"row_index": idx, **result.model_dump()})
            continue

        stub      = str(row.get("description", "") or "").strip()
        full_text = load_full_text(row)

        try:
            result = call_api(client, stub, full_text)
            result = post_process(result)

            with open(cache_path, "w") as f:
                f.write(result.model_dump_json())

            results.append({"row_index": idx, **result.model_dump()})

        except Exception as e:
            errors.append({"row_index": idx, "error": str(e)})
            tqdm.write(f"  ERROR row {idx}: {e}")

    # ------------------------------------------------------------------
    # Write output CSV
    # ------------------------------------------------------------------
    results_df = pd.DataFrame(results)

    list_cols = [
        "skill_categories_required", "skill_categories_preferred",
        "skill_categories_mentioned", "certifications_required",
        "certifications_preferred", "certifications_substitutable",
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

    print("\n=== Text selection summary ===")
    if "text_used" in results_df.columns:
        print(results_df["text_used"].value_counts().to_string())

    print("\nNext step:")
    print("  python3 skills_analysis/02_merge_outputs.py")


if __name__ == "__main__":
    main()
