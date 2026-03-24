# Skill Taxonomy for Election Official Job Description Analysis

**Status:** DRAFT — awaiting Will's review
**Last updated:** 2026-03-23

---

## How This Taxonomy Was Developed

The taxonomy was developed inductively from a stratified sample of 12 job postings read in full. This is a standard qualitative content analysis approach: read a sample, identify recurring themes, group them into categories, refine until no new themes emerge.

**Sampling procedure** (reproduced exactly by `00_develop_taxonomy.py`):
- Restricted to `rich_full_text` files (≥3,000 chars, passing junk checks) classified as `election_official` or `top_election_official`
- Stratified into four eras: 2013–2016 (2 postings), 2017–2019 (3), 2020–2022 (3), 2023–2025 (4)
- Random sample within each era using a fixed seed (42 + era start year)

The canonical reproducible sample is the one `00_develop_taxonomy.py` currently produces. The initial taxonomy draft was developed from a closely related sample drawn under the same parameters; the categories are robust to minor variation in which specific postings are included.

**Inductive process:** For each posting, we identified all explicitly stated skills, qualifications, and competency requirements. We grouped similar items across postings and iteratively refined the category boundaries. The resulting 13 categories reflect the actual language of the postings, not a pre-existing framework imposed from outside.

**For the paper's methods section**, this can be described as: *"We developed the skill taxonomy inductively through content analysis of a stratified sample of N postings drawn across four time periods (2013–2016, 2017–2019, 2020–2022, 2023–2025). For each posting, we identified all explicitly stated skills, qualifications, and competency requirements and grouped them into categories based on conceptual similarity, refining iteratively until no new themes emerged."*

---

## Design Decisions

**Required vs. Preferred:** Track separately where the posting makes the distinction explicit. Many recent postings use clear "Minimum Qualifications" / "Preferred Qualifications" sections. For early postings (especially stubs) that don't separate them, code as "required" by default. LLM prompt should return both lists.

**Counting unit:** Binary presence per category (0/1) is the primary unit. Also track a total count (number of categories present). Do NOT try to count individual bullet points — too noisy across posting formats.

**Formal qualifications vs. skills:** Treat as a separate dimension, since a degree requirement is categorically different from a demonstrated skill. Credentials (CERA, PMP, etc.) are tracked within the formal qualifications category.

**Role-level coding:** Use the existing `classification_experimental` column (top_election_official, election_official, not_election_official) for stratification — do not re-code job level from scratch.

---

## Taxonomy

### Category 1: Election Operations & Administration
**Core concept:** Direct hands-on administration of elections — everything that goes into running an election.

Includes:
- Ballot preparation, design, printing, mailing
- Voting equipment (setup, testing, maintenance, transportation)
- Poll worker / election officer recruitment, training, deployment
- Absentee / mail ballot processing
- Election Day coordination and logistics
- Canvassing, certifying results
- Precinct management (number, boundaries, polling site accessibility)
- Candidate filing, petition verification
- Campaign finance disclosure administration

*Grounding examples: Pierce County Election Clerk 2 (2019); Alexandria Elections Manager (2022); New Hanover Elections Director (2025)*

---

### Category 2: Voter Registration Systems
**Core concept:** Management of the voter rolls — database operations, compliance, list maintenance.

Includes:
- State voter registration database operations (data entry, updates, records research)
- NVRA compliance (National Voter Registration Act)
- List maintenance (deceased voters, address changes, duplicates)
- Online/DMV/DOL registration processing
- Verifying voter eligibility and status
- Processing candidate and party registration materials

*Grounding examples: Pierce County Election Clerk 2 (2019 — heavy VR data entry); Solano County Election Coordinator (2019 — statewide VR database)*

---

### Category 3: Legal & Regulatory Compliance
**Core concept:** Knowledge of and ability to interpret the governing legal framework for elections.

Includes:
- Federal election law (HAVA, Voting Rights Act, NVRA, ADA/accessibility)
- State election code / statutes interpretation and implementation
- Local ordinances and rules
- Analyzing proposed legislation / regulatory changes
- Enforcing legal requirements (deadlines, filing requirements)
- Obtaining and applying legal opinions
- Campaign finance law

*Grounding examples: Solano County (2019 — "researching and applying State and Federal laws"); Alexandria Elections Manager (2022 — "complex and continually changing laws"); New Hanover Director (2025 — "NC General Statutes")*

---

### Category 4: IT, Cybersecurity & Election Technology
**Core concept:** Technology competencies specific to election administration — from election management systems to network security.

Includes:
- Election Management System (EMS) operation / configuration
- Voting system hardware/software (programming, testing, certification)
- Cybersecurity fundamentals as applied to elections
- Network security, data security, system integrity
- IT troubleshooting / technical support
- Election technology evaluation and procurement

*Grounding examples: Boulder County Elections Technology Specialist (2015); Fairfax General Registrar (2021 — "cybersecurity fundamentals"; "information technology and its uses to enhance election performance")*

Note: This category has shown clear time-series signal — worth tracking separately from general IT.

---

### Category 5: Data Management & Analysis
**Core concept:** Working with data beyond VR database maintenance — analysis, reporting, decision support.

Includes:
- Database management (design, query, reporting)
- Statistical / quantitative analysis
- Excel (pivot tables, data analysis)
- Data analytics and reporting for decision-making
- Demand forecasting, process metrics
- Business intelligence tools

*Grounding examples: Fairfax General Registrar (2021 — "Microsoft Office 365, Excel pivot tables and data analysis; database management fundamentals; data analytics")*

---

### Category 6: Project Management & Logistics
**Core concept:** Managing complex, time-sensitive, multi-part operations — a distinct competency from election operations themselves.

Includes:
- Planning and scheduling multi-phase election cycles
- Meeting statutory deadlines under time pressure
- Multi-task / concurrent project coordination
- Risk management
- Process improvement and change management
- Large-scale logistics (managing hundreds of locations, large temporary workforces)
- Vendor and contract management

*Grounding examples: Fairfax General Registrar (2021 — "plan, organize, and direct large, complex, logistical operations"; "risk management; process improvement & change management")*

---

### Category 7: Personnel Management & Supervision
**Core concept:** Hiring, supervising, developing, and evaluating staff — including large pools of temporary election officers.

Includes:
- Hiring and onboarding
- Staff supervision and evaluation
- Training design and delivery
- Managing temporary/seasonal/volunteer workforces (often 100s–1000s of poll workers)
- Resolving personnel issues / HR compliance
- Staff development and mentoring
- Union/labor relations (where applicable)

*Grounding examples: Contra Costa Elections Services Manager (2016); Fairfax General Registrar (2021 — 200 temps, 3700 election officers)*

---

### Category 8: Budget & Financial Management
**Core concept:** Fiscal responsibility — from annual budgeting to election cost estimation and grant management.

Includes:
- Annual budget preparation and management
- Expenditure tracking and oversight
- Election cost estimation and billing (e.g., jurisdictions served)
- State mandate reimbursement claims
- Grant management and compliance
- Procurement and contracting
- Financial reporting and audit compliance

*Grounding examples: Contra Costa Manager (2016 — "estimating election costs and reviews billings"); Fairfax General Registrar (2021 — "multi-million dollar budget")*

---

### Category 9: Public Communication & Outreach
**Core concept:** External-facing communication — to voters, media, candidates, and the public.

Includes:
- Media relations and press inquiries
- Public speaking and presentations
- Community outreach and voter education programs
- Written communications (press releases, reports, fact sheets)
- Social media and digital communications
- Candidate/political party coordination
- Crisis communications
- Multi-cultural outreach and community relations

*Grounding examples: EAC Communications Specialist (2022); New Hanover Director (2025 — "non-partisan position promoting understanding, confidence, and trust")*

---

### Category 10: Intergovernmental & Stakeholder Coordination
**Core concept:** Working across jurisdictions and with external agencies — distinct from general public outreach.

Includes:
- Coordination with state election authority / State Board of Elections
- Liaising with federal agencies (EAC, DOJ, DHS/CISA)
- Working with other county departments, cities, school districts, special districts
- Professional associations (NASS, NASED, EAC clearinghouse, state associations)
- Political parties and candidates
- Advocacy groups and outside organizations

*Grounding examples: Contra Costa (2016 — "election activities with other County agencies, cities, schools, special districts, and the State"); Fairfax (2021 — "government officials, the media, political parties, and the general public")*

---

### Category 11: GIS, Mapping & Redistricting
**Core concept:** Geographic information systems as applied to election administration.

Includes:
- GIS software operation
- Precinct boundary management and redistricting implementation
- Mapping voter precincts, polling locations
- Spatial analysis for accessibility or voter assignment

*Present in some postings; rarer in stubs. Worth tracking as a distinct competency even if low-frequency.*

---

### Category 12: Bilingual / Language Skills
**Core concept:** Non-English language requirements or preferences.

Includes:
- Any specific language requirement or preference (Spanish most common)
- Section 203 VRA language minority obligations

*Appears in subset of postings; straightforward binary flag.*

---

### Category 13: Formal Qualifications
**Core concept:** Credentials, degrees, and certifications explicitly required or preferred.

Tracks the following as sub-items:
- **Degree level:** High school / associate / bachelor's (required) / bachelor's (preferred) / master's
- **Degree field:** Public administration, political science, business, other specified, or any field
- **Years of experience:** Minimum required years of relevant experience
- **Experience substitution:** Whether experience can substitute for degree
- **Professional certifications:**
  - CERA (Certified Elections/Registration Administrator — Auburn/Election Center)
  - CME (Certified Municipal/County Election Official — varies by state)
  - CalPEAC (California)
  - NC Election Administrator certification
  - PMP (Project Management Professional)
  - CPA / auditing certifications
  - Other state-specific credentials

*This is a separate dimension — track whether each credential appears as required, preferred, or substitutable.*

---

## Summary Table

| # | Category | Short Code | Notes |
|---|---|---|---|
| 1 | Election Operations & Administration | `ops` | Core function; present in nearly all |
| 2 | Voter Registration Systems | `vr` | Core function; especially clerk roles |
| 3 | Legal & Regulatory Compliance | `legal` | Universal but depth varies |
| 4 | IT, Cybersecurity & Election Technology | `it_cyber` | Growing; track as own category |
| 5 | Data Management & Analysis | `data` | Growing; separate from VR database ops |
| 6 | Project Management & Logistics | `pm` | Often implicit; explicit in senior roles |
| 7 | Personnel Management & Supervision | `personnel` | Varies by level |
| 8 | Budget & Financial Management | `budget` | Present in mid+ level roles |
| 9 | Public Communication & Outreach | `comms` | Growing; includes voter ed |
| 10 | Intergovernmental & Stakeholder Coordination | `intergovt` | Growing; explicit in senior roles |
| 11 | GIS, Mapping & Redistricting | `gis` | Low-frequency specialty |
| 12 | Bilingual / Language Skills | `bilingual` | Binary flag |
| 13 | Formal Qualifications | `quals` | Separate dimension; sub-items for degree/cert |

---

## LLM Extraction JSON Schema (draft)

```json
{
  "skill_categories_required": ["ops", "vr", "legal"],
  "skill_categories_preferred": ["it_cyber", "gis"],
  "skill_categories_mentioned": ["ops", "vr", "legal", "it_cyber"],
  "total_category_count": 4,
  "election_security_explicit": false,
  "formal_quals": {
    "degree_required": "bachelor",
    "degree_field": "public administration or related",
    "min_years_experience": 5,
    "experience_can_substitute": true,
    "certifications_required": [],
    "certifications_preferred": ["CERA", "PMP"],
    "certifications_substitutable": ["CERA"]
  },
  "text_confidence": "high",
  "extraction_notes": "Clear required/preferred distinction in posting. Rich full text."
}
```

Note: `election_security_explicit` is a boolean flag within Category 4 (IT/Cybersecurity). Set to true only when the posting uses language specifically about election security as a distinct competency (e.g., "election security", "securing elections", "CISA coordination") — not just general IT or cybersecurity language. This captures the post-2016 signal without fragmenting the category.

`certifications_substitutable` lists credentials that appear in "substitution" clauses, i.e., where the posting says the credential can replace a year of experience or education. CERA appears this way frequently.

`text_confidence` values:
- `"high"` — rich full text with clear qualifications sections
- `"medium"` — marginal full text or stub with some skill mentions
- `"low"` — very short stub, only partial information available

---

## Design Decisions (Resolved)

**Q1 — Categories 9 & 10 (Intergovernmental vs. Public Comms):** Keep separate. Different competencies for our purposes.

**Q2 — Election security as sub-category:** Too granular given our N. Middle ground: add a boolean flag `election_security_explicit` within Category 4. The LLM returns this as a sub-field (true/false) inside the IT/Cybersecurity result. This captures the post-2016 time-series signal without fragmenting the category counts.

**Q3 — CERA as substitute:** Track it. The JSON schema now includes `certifications_substitutable` as a sub-field alongside `certifications_required` and `certifications_preferred`.

**Q4 — EAC and classification reliability:** EAC postings are not election officials (they don't run elections) and should be excluded from the primary trend analysis. More broadly, the `classification_experimental` column is unreliable and should be rebuilt — see note in the JSON schema section and the reclassification plan in `RESEARCH_PLAN.md`.