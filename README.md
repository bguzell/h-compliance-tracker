# New York Hospital Financial Assistance Compliance Tracker

**Community-partner prototype: Community Service Society of New York (CSSNY)**  
**Columbia University Data Science Institute — AI for Health Equity Design Sprint, Track 2**

A traceable, public-interest hospital financial-assistance monitoring prototype. The 2025 CSSNY manual review is an **archival baseline**; it is never presented as current evidence. **Live grades remain pending/provisional until source documents are retrieved and verified.** No patient eligibility advice.

## What is implemented

- 212 2025 baseline facilities, keyed by `OCN_PFI` (not hospital name). One record lacks PFI and OCN: it receives a deterministic **UNRESOLVED** temporary identifier and a reconciliation warning.
- Idempotent SQLAlchemy/SQLite import; clean separation of 2025 manual grades and current evidence assessments.
- All **17 CSSNY measures** with exact baseline column names and 4 evidence scopes; deterministic A/B/C/D/F logic and configurable automatic-F rules.
- Website/PDF/DOCX retrieval, candidate-source provenance tracking, cautious same-hospital link discovery, content size limits, URL validation, robots handling, bounded retries, native PDF extraction and optional OCR. Errors are displayed as REVIEW; they never become invented compliance violations.
- Evidence-bearing `PASS`, `FAIL`, `REVIEW`, `N/A`; excerpt, URL, document type, source time, explanation and extraction method. No model decides grades.
- Optional LLM extraction via OpenAI-compatible API or AWS Bedrock: literal quote verification; extracted candidates remain **REVIEW** until deterministic checks or human confirmation.
- Structured cross-document checks, separate application/summary evaluation, hash-based current-state replacement, tiny change log, reviewer decisions bound to the exact current document hash.
- Public Streamlit dashboard, historical distribution, map where **official coordinates** have been reconciled, filters, source-backed hospital detail pages, methods and password-protected review queue.
- NYSDOH Socrata roster integration, application reference year checking, a daily lightweight conditional retrieval and a weekly full re-evaluation in a **separate scheduler process**.
- Automated regression, scope, source-security, source-failure, extraction and hallucination checks.

## Quick start (Python 3.11+)

```bash
unzip hfap_tracker.zip
cd hfap_tracker
python -m venv .venv
source .venv/bin/activate                  # Windows: .venv\\Scripts\\activate
python -m pip install -r requirements.txt
cp .env.example .env
# set a strong HFA_ADMIN_PASSWORD in .env to enable human-review actions
python -m src.cli seed
python -m src.cli validate                 # verifies all 212 historical records
python -m pytest -q                       # automated regression/security checks
streamlit run app.py                       # visit http://localhost:8501
```

**Current data is initially not checked.** Historical data can be explored immediately; source-backed current results only appear after refreshing. This is deliberate, not a dashboard malfunction.

### Refresh real hospital sources and build a map

```bash
python -m src.cli fpl-standard           # confirm applicable year from official DOH listing
python -m src.cli roster                 # match PFI/address to official NYSDOH facility coordinates
python -m src.cli refresh --limit 3      # safe initial smoke test on three hospitals
python -m src.cli refresh                # evaluate all 212 hospital HFA pages
python -m src.cli daily                  # lightweight conditional daily check
python -m src.scheduler                  # long-running worker (separate terminal/service)
```

For higher reliability run `python -m src.cli refresh --limit 3` in an internet-connected environment first; inspect the evidence pages and source warnings before running statewide. Strict crawlers may not follow CDN links, JS portals, or external forms; such facilities stay REVIEW. A complete, reliable 212-site live assessment cannot be claimed without a real crawl and qualified manual verification.

### Important: 38 original hyperlink cells are not URLs

Exactly **38 of the 212** 2025 hyperlink cells contain webpage titles instead of actual URLs. The original historical CSVs are preserved, and `data/seed/hfa_url_overrides.csv` contains 38 proposed official-hospital or official-system HFA starting URLs with the original text, verification provenance, and evidence references. **None of these reconstructed URLs have been fetched from the application runtime; check them before interpreting a current assessment.** A shared health-system page is only a discovery candidate; it never automatically transfers another facility's results. The system withholds every decision until an authorized reviewer verifies facility coverage. See `docs/url_resolution_report.md`.

To approve a shared-system source after inspecting the actual current materials, first refresh the specific hospital, then run:

```bash
python -m src.cli verify-source --hospital-id 'OCN_PFI' \
  --evidence-url 'https://official-hospital-source-url' \
  --note 'Describe the exact official evidence demonstrating this particular facility is covered.'
python -m src.cli refresh    # recomputes the newly verified facility assessment
```

An evidence URL must match a **successfully retrieved current source document**, and verification is logged. This step is *not* implied simply by common system membership.

**Docker (two services with shared persistent SQLite volume):**

```bash
export HFA_ADMIN_PASSWORD='choose-a-long-unique-password'
docker compose up --build -d
# dashboard: http://localhost:8501
# run initial authoritative geodata/refresh in a separate one-off container:
docker compose exec dashboard python -m src.cli roster
docker compose exec dashboard python -m src.cli fpl-standard
docker compose exec dashboard python -m src.cli refresh --limit 3
```

For production scale, move to managed PostgreSQL (`HFA_DATABASE_URL`), persist worker logs, provide a monitored scheduler, manage secrets via a secret store, add reviewer identity / RBAC, expert approval workflows and operational alerting. **Streamlit Community Cloud alone will not run a reliable persistent scheduler.** Use a separate worker/container for the scheduled checks.

## Architecture

```text
CSSNY CSV -> seed/reconciliation -----------------------> Hospital (current + historical metadata)
                 NYSDOH geodata ------------------------> coordinates + roster flags

hospital HFA URL -> safe crawler -> PDF/DOCX/HTML extract -> source-linked facts
                         |                                  |
                         |--- current hashes (replace) -----|
                         |                                  v
                         |                     application-only checks
                         |                     summary-only checks
                         |                     overall and cross-document checks
                         |                                  |
                         |                     deterministic grading + REVIEW
                         |                                  |
                         +-- change metadata -------------> SQLite/Postgres
                                                             |
                                                 Streamlit + review queue
```

`src/criteria.py` has all 17 field definitions and patient impact statements; `src/extractor.py` contains the deterministic evidence rules; `src/grader.py` alone calculates grades; `src/updater.py` controls current-only persistence. `app.py` and `pages/` are UI-only.

## Historical validation

The original 2025 tracker contains **212 facilities** and these exact grades:

| 2025 grade | Facility count |
|---|---:|
| A | 14 |
| B | 116 |
| C | 31 |
| D | 10 |
| F | 41 |

Applying the historical `Noncompliant Categories Count` + `Automatic Fail?` gives **zero mismatches**. However, **17 non-F records** lack a policy statement: the PDF methodology requires an automatic F, while the source spreadsheet did not apply this rule consistently. `docs/baseline_validation.json` lists every disagreement. The default *new-assessment* policy uses the PDF's rule and is controlled by `HFA_AUTO_FAIL_MISSING_POLICY_STATEMENT=true`. **CSSNY should adjudicate this difference.** Historical values remain intact.

Other unresolved issues: legal interpretation of bank-statement requests; verifying 2007 service-area boundaries against hospital-specific primary service areas; and proving that an application is the *entire* current NYSDOH Uniform Application. These are queued for human review, not guessed.

## Current legal reference (verified November 2026)

- [NYSDOH Patient Financial Aid Law](https://www.health.ny.gov/facilities/hospital/financial_assist/) — 2024 revisions, application requirement, 400% FPL, immigration rule.
- [NYSDOH hospital guidance & Uniform Application](https://www.health.ny.gov/facilities/hospital/financial_assist/hosp_info/) — a **2026** Uniform Application is listed.
- [NYS Public Health Law §2807-k](https://www.nysenate.gov/legislation/laws/PBH/2807-K) — current text; application requirement, summary, installments, no limited application time, service-area provisions.
- [NYSDOH Health Facility General Information (Socrata)](https://health.data.ny.gov/Health/Health-Facility-General-Information/vn5v-hh5r) — authoritative facility roster and geographic coordinates (dataset updated October 2026).

The applicable reference year is not fixed in code: `python -m src.cli fpl-standard` reads NYSDOH’s official listing into `data/current/fpl_standard.json`, with fallback `HFA_CURRENT_FPL_YEAR=2026` if the source cannot be accessed. Recheck it when annual guidance changes.

## Testing and scope limits

Run `python -m pytest -q`. The supplied package was validated against **40 passing automated tests** and **0 historical-grade mismatches** in the execution environment. **Streamlit and APScheduler were not installed in the build environment, so a live browser smoke test and deployed scheduler run were not possible here.** Install `requirements.txt` before launching. Network access to external hospital websites was unavailable during repository creation; **no current hospital grades or geographic coordinates have been fabricated**. See `docs/live_refresh_status.csv` for all initial statuses.

This is an evidence-first, research-facing prototype, not a legally authoritative determination of a hospital's obligations. Do not assume a patient is eligible or ineligible based on a dashboard grade.

## Demo in five minutes

1. **Equity problem:** open dashboard and show the CSSNY 2025 results alongside transparent *current evidence pending* status.
2. **Statewide infrastructure:** show facility IDs, search/filter, and the official-coordinate map once the roster sync has run.
3. **Patient-facing explainability:** choose one hospital; expand a criterion for “what the rule requires / why it matters / evidence / official source.”
4. **Ethical guardrail:** simulate a broken site (or show a source-unavailable warning); it becomes REVIEW, never an invented F.
5. **Accountability:** show methodology discrepancy and the source-hash-bound reviewer queue, then discuss daily/weekly monitoring.
