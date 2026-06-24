# Project Guide — AI Job Automation

> **Purpose of this file.** This is the single source of truth for how this project works.
> It is written so that a human contributor **or an AI assistant** can read it once and then
> explain the system, change it safely, and adapt it to a different job search.
> If you change behaviour in the code, **update this file in the same change.**

---

## Table of Contents

1. [What this project does](#1-what-this-project-does)
2. [Core principles (what it considers and ignores)](#2-core-principles-what-it-considers-and-ignores)
3. [Quick start](#3-quick-start)
4. [End-to-end data flow](#4-end-to-end-data-flow)
5. [Sources: APIs, scrapers, and placeholders](#5-sources-apis-scrapers-and-placeholders)
6. [The `Job` data model](#6-the-job-data-model)
7. [Input: CLI options and environment variables](#7-input-cli-options-and-environment-variables)
8. [Output: CSV / Excel / Word / Sheets / Notion](#8-output-csv--excel--word--sheets--notion)
9. [Scoring metrics (exact weights)](#9-scoring-metrics-exact-weights)
10. [Detection and enrichment modules](#10-detection-and-enrichment-modules)
11. [Filtering: dedup, company size, min-score](#11-filtering-dedup-company-size-min-score)
12. [Tests](#12-tests)
13. [Optimizations and design decisions already made](#13-optimizations-and-design-decisions-already-made)
14. [How to customize this for YOUR job search](#14-how-to-customize-this-for-your-job-search)
15. [Roadmap and where to extend](#15-roadmap-and-where-to-extend)

---

## 1. What this project does

A Python MVP that **discovers, ranks, and exports junior-level job postings** in:

- AI automation / applied AI
- AI agents / agentic systems / LLM automation
- no-code & low-code automation (n8n, Make.com, Zapier)
- workflow / process automation, AI solutions & implementation

It collects **public** postings from several sources, normalizes them into one schema,
detects language / seniority / remote type / region / company size, removes duplicates,
**scores each job 0–100**, stores everything in SQLite, and writes human-friendly exports
(Excel, Word, CSV) plus optional Google Sheets / Notion.

The default target persona is a **junior** candidate looking for **remote/hybrid** roles in
**DACH / Europe / worldwide-remote**, with a salary and weekly-hours preference. All of that
is configurable — see [section 14](#14-how-to-customize-this-for-your-job-search).

---

## 2. Core principles (what it considers and ignores)

**Considers (boosts the score):** target titles, junior signals, remote/hybrid, AI + automation
skills, target geography, supported languages, startup signals, salary ≥ target, weekly hours ≤ target.

**Down-ranks or rejects:** senior/lead/staff/director signals, "5+ years experience", onsite-only
outside target regions, pure QA/test-automation noise, weak role fit, and clearly unrelated titles
(graphic designer, customer support, industrial/PLC automation, etc.).

**Hard rules (drop entirely, never exported):**

- **Companies with more than 200 employees** are removed before scoring/export. Unknown company
  size is **kept** for manual review (see [section 11](#11-filtering-dedup-company-size-min-score)).
- **Duplicates** across sources are removed.
- Jobs below `--min-score` are not exported (but still stored in SQLite).

**Scraping ethics (built into the design):** the project prefers official APIs, public JSON/RSS
feeds, search APIs, sitemaps, and manual imports. It deliberately **avoids** scraping login/CAPTCHA
walled or anti-bot-protected boards (LinkedIn, Indeed, Glassdoor, …). Those domains are listed in
`scrapers/generic_search_scraper.py` (`blocked_domains`) and explained in `SCRAPER_ROADMAP.md`.

---

## 3. Quick start

Requirement: **Python 3.11+**.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
copy .env.example .env          # cp on macOS/Linux
```

Run against offline mock data (no network, no API keys):

```bash
python main.py --sources mock --limit 10 --region europe --remote true --min-score 60 --export all
```

Run against the free public-API sources:

```bash
python main.py --region europe --remote true --min-score 60 --sources remoteok,remotive,arbeitnow,weworkremotely --export xlsx
```

Exports land in `data/exports/`. Logs in `data/logs/job_automation.log`.

Run the tests:

```bash
pytest
```

> On some Windows setups (e.g. project under OneDrive) pytest's temp/cache dirs can hit permission
> errors. Workaround: `pytest -p no:cacheprovider --basetemp=.pytmp`.

---

## 4. End-to-end data flow

Everything is orchestrated by `run()` in [`main.py`](main.py):

```
selected_scrapers(sources, limit)        # pick scraper classes from SCRAPER_REGISTRY
  └─ scraper.search(region, remote)      # each source returns list[Job]
        → raw_jobs
deduplicate_jobs(raw_jobs)               # matching/deduplication.py
  → unique_jobs
score_jobs(unique_jobs)                  # per job:
  ├─ prepare_deduplication(job)          #   normalize title/company/url + dedup key
  ├─ apply_score_breakdown(job)          #   matching/scorer.py → relevance_score + sub-scores
  ├─ classify_company_fit(job)           #   startup / sme / enterprise / unknown
  ├─ priority_from_score(score)          #   urgent / high / medium / low
  └─ explain_score(job)                  #   human-readable "why" string
  → sort by relevance_score desc
FILTER: drop companies > MAX_COMPANY_EMPLOYEES   # matching/company_intel.exceeds_employee_limit
  → scored_jobs
db.upsert_jobs(scored_jobs)              # database/db.py (SQLite, upsert on deduplication_key)
FILTER: keep relevance_score >= min_score
  → exportable_jobs
exporters:  csv / xlsx / docx  (+ google sheets / notion if enabled)
```

The order matters: **scoring → size filter → store → min-score filter → export.** The size filter
runs before storage so over-200-employee companies are never persisted or shown.

---

## 5. Sources: APIs, scrapers, and placeholders

Sources are registered in `SCRAPER_REGISTRY` in [`main.py`](main.py) and selected with `--sources`.
Default when `--sources` is omitted: `remoteok, remotive, arbeitnow, weworkremotely, yc, generic`.

| Key (`--sources`) | Type | Needs key? | How it works |
|---|---|---|---|
| `remoteok` | Public JSON API | No | `GET remoteok.com/api`, parses positions/tags/salary. |
| `remotive` | Public JSON API | No | `GET remotive.com/api/remote-jobs?search=...` across ~10 AI/automation queries. |
| `arbeitnow` | Public JSON API | No | `GET arbeitnow.com/api/job-board-api` pages 1–3 (Germany/EU focused). |
| `weworkremotely` | Public RSS feed | No | Parses the `/remote-jobs.rss` feed (the HTML search 403s non-browsers; the feed is published for consumption). Keeps AI/automation-relevant items. |
| `generic` | **Search API + page fetch** | **Yes (SerpAPI)** | The self-built search scraper. Builds targeted queries, calls SerpAPI, filters noise, optionally fetches each job-detail page for richer text. See `SCRAPER_ROADMAP.md`. |
| `cached` | **Replays SerpAPI captures** | No | Re-parses previously captured SerpAPI responses (`SERPAPI_CAPTURE_DIR`) into jobs offline — keeps the value of past paid searches without spending new credits. |
| `ats` | **ATS JSON APIs** | No | Key-free scraper for Greenhouse + Lever + Ashby + Workable public job boards. Reads company slugs from `companies.yaml`, keeps AI/automation-relevant titles, maps to `Job`. This is the recommended SerpAPI-free path — see `SCRAPER_ROADMAP.md`. |
| `hackernews` | **HN Algolia API** | No | Parses the monthly "Ask HN: Who is hiring?" thread (key-free). Extracts company/role/location/remote from each top-level comment; keeps only AI/automation-relevant postings. Rich in AI startups. |
| `rss` | **RSS/Atom feeds** | No | Generic feed scraper (Himalayas, WeWorkRemotely categories, Jobspresso by default; add more via `RSS_FEEDS`). Extracts the company from a `<company>`/`<companyName>`/`<dc:creator>` tag or a "Company: Role" title; title-based relevance filter. |
| `mock` | Offline fixtures | No | `scrapers/mock_website_scraper.py` — deterministic jobs for testing the whole pipeline offline. |
| `manual` | CSV import | No | Reads `manual_jobs.csv` (same columns as the `Job` model). |
| `yc`, `wellfound`, `join`, `germantechjobs`, `berlinstartupjobs` | **Placeholders** | No | Return `[]` and log a note. They exist as extension points; these boards are JS-heavy or ToS-sensitive and should be reached via approved APIs/feeds, not raw scraping. |

**SerpAPI gating.** `generic` only runs when `SERPAPI_API_KEY` is set in `.env`. Each generated query
consumes one SerpAPI credit, so `--limit` on the `generic` source caps the number of queries. Without
a key it logs and returns nothing — use the free API sources or `mock` instead.

**To run without SerpAPI:** use `--sources ats` (plus the free API sources). Put your target company
slugs in `companies.yaml` and the `ats` source fetches their Greenhouse/Lever/Ashby/Workable boards
directly — no key, no blocking. To populate `companies.yaml` automatically, spend a small SerpAPI budget
once with `python discover_ats_companies.py --limit 12` (discovers ~100 ATS slugs), then fetch their jobs
for free thereafter. Prune large companies from the file by hand. The `SEARCH_BACKEND` env var (`serpapi` / `crawler` / `auto`) is the planned explicit
toggle; full auto-routing arrives with the discovery loop (see [`SCRAPER_ROADMAP.md`](SCRAPER_ROADMAP.md)).

All scrapers share one polite HTTP layer (`scrapers/http_client.py`): per-host rate limiting with
jitter, retries with exponential backoff honoring `Retry-After`, and a rotating pool of honest
User-Agent strings.

---

## 6. The `Job` data model

Defined in [`database/models.py`](database/models.py) (Pydantic). Every source maps its raw data into
this schema and calls `BaseScraper.normalize_job()`. Key fields:

- **Identity / display:** `job_title`, `company_name`, `location`, `city`, `country`, `region`,
  `remote_type`, `seniority`, `language`, `salary`, `job_url`, `job_description`, `required_skills`.
- **Company intel:** `company_size`, `company_size_source`, `company_stage`, `company_fit`,
  `is_startup_likely`.
- **Scoring:** `relevance_score` + sub-scores (`title_fit_score`, `seniority_fit_score`,
  `remote_fit_score`, `skill_fit_score`, `geography_fit_score`, `compensation_fit_score`,
  `company_fit_score`, `penalty_score`), `priority_level`, `reason_for_score`.
- **Workflow:** `application_status`, `review_notes`, `next_step`.
- **Provenance / dedup:** `source_platform`, `source_type`, `date_found`, `date_posted`,
  `normalized_title`, `normalized_company`, `deduplication_key`, `created_at`, `updated_at`.

`Job.text_blob()` concatenates the searchable text fields; scoring and detection run against it.

---

## 7. Input: CLI options and environment variables

### CLI (`python main.py ...`)

| Option | Default | Meaning |
|---|---|---|
| `--region` | `worldwide` | `germany`, `dach`, `europe`, `asia`, `america`, `worldwide`. |
| `--remote` | `true` | `true`/`false`. |
| `--min-score` | `60` (`DEFAULT_MIN_SCORE`) | Minimum score to export. |
| `--export` | `xlsx` | `xlsx` / `docx` / `csv` / `both` (csv+xlsx) / `all` (csv+xlsx+docx) / `none`. |
| `--sources` | (the six defaults) | Comma-separated source keys from the table above. |
| `--limit` | `50` (`MAX_JOBS_PER_SOURCE`) | Max jobs per source (for `generic`, max queries). |
| `--dashboard` | `false` | Print the Streamlit launch hint. |

### Environment variables (`.env`, loaded by `config.py`)

| Variable | Default | Effect |
|---|---|---|
| `MAX_COMPANY_EMPLOYEES` | `200` | Upper employee limit; companies above it are dropped. |
| `DEFAULT_MIN_SCORE` | `60` | Default export threshold. |
| `MAX_JOBS_PER_SOURCE` | `50` | Default per-source limit. |
| `SCRAPER_RATE_LIMIT_SECONDS` | `2` | Per-host delay between HTTP requests (shared HTTP client). |
| `HTTP_MAX_RETRIES` | `3` | Retry attempts on transient HTTP errors (429/5xx/timeouts). |
| `HTTP_JITTER_SECONDS` | `0.75` | Random jitter added to rate-limit and backoff waits. |
| `HTTP_RESPECT_ROBOTS` | `true` | Honor each host's robots.txt; disallowed URLs are skipped. |
| `HTTP_ENABLE_CACHE` | `true` | Conditional requests: remember ETag/Last-Modified, reuse on 304. |
| `HTTP_CIRCUIT_BREAKER_THRESHOLD` | `5` | Consecutive per-host failures before the host is skipped for the run. |
| `SEARCH_BACKEND` | `auto` | `serpapi` / `crawler` / `auto` (informational today; see roadmap). |
| `COMPANIES_FILE` | `companies.yaml` | Path to the ATS slug list used by `--sources ats`. |
| `RSS_FEEDS` | (built-in set) | Comma-separated RSS/Atom feed URLs for the `rss` source. |
| `SERPAPI_API_KEY` | — | Enables the `generic` SerpAPI search path. |
| `SERPAPI_FETCH_DETAILS` | `true` | If false, the `generic` scraper skips slow job-detail page fetches. |
| `SERPAPI_CAPTURE_DIR` | — | If set, dumps each raw SerpAPI response there so parsing can be iterated offline (no extra credits). |
| `BING_SEARCH_API_KEY`, `GOOGLE_SEARCH_API_KEY` | — | Recognized but parsing not yet implemented. |
| `GOOGLE_SHEETS_ENABLED` + `GOOGLE_SHEETS_CREDENTIALS_PATH` + `GOOGLE_SHEETS_ID` | off | Google Sheets export. |
| `NOTION_ENABLED` + `NOTION_API_KEY` + `NOTION_DATABASE_ID` | off | Notion export. |
| `ENABLE_PLAYWRIGHT`, `HEADLESS_BROWSER` | off / on | For future JS-rendered sources. |

`.env` is **git-ignored** (it holds secrets). `.env.example` is the safe template to copy.

---

## 8. Output: CSV / Excel / Word / Sheets / Notion

All exporters consume a uniform list of records produced by
[`exporters/job_presenter.py`](exporters/job_presenter.py) (`build_job_records`), which also runs the
compensation/hours analysis per job.

- **CSV** — `exporters/csv_exporter.py`, raw flat export.
- **Excel** — `exporters/xlsx_exporter.py`. Two sheets:
  - **Overview**: summary stats + a compact ranked table (Score, Priority, Status, Title, Company,
    Company Type, **Company Size**, **City**, **Country**, Location, Remote, Compensation, Skills, Link, Dismissed?).
  - **Job Details**: the full column set (`XLSX_COLUMNS`) with score breakdown, comp/hours flags,
    conditional formatting (score & yes/no coloring), dropdown validation (`Status`, `Dismissed?`),
    and a strike-through rule for dismissed rows. **This is the human review surface** — edit it and
    regenerate Word from it.
- **Word** — `exporters/docx_exporter.py`. One card per job with company type, **company size**,
  **city/country**, link, compensation, skills, "why it matches", and description.
- **Google Sheets / Notion** — `exporters/google_sheets_exporter.py`, `exporters/notion_exporter.py`;
  no-ops unless enabled in `.env`.

### Excel → Word (review-driven)

`export_word_from_excel.py` reads an **edited** Excel workbook (the `Job Details` sheet) and produces a
Word report. It honors your edits: rows marked `Dismissed? = yes` or `Status = dismissed` are excluded,
**and rows whose `Company Size` exceeds 200 employees are excluded too** (same rule as the pipeline).

```bash
python export_word_from_excel.py                       # latest pretty Excel, drop dismissed
python export_word_from_excel.py --include-dismissed true
python export_word_from_excel.py --excel data/exports/jobs_export_YYYY-MM-DD_pretty.xlsx
```

---

## 9. Scoring metrics (exact weights)

Implemented in [`matching/scorer.py`](matching/scorer.py) → `calculate_score_breakdown()`. The final
`relevance_score` is `clamp(sum of all components, 0, 100)`.

**Positive components**

| Component | Points | Trigger |
|---|---|---|
| `title_fit_score` | +25 | title matches a `TARGET_TITLES` entry |
| `title_fit_score` | +5 | title contains a `ROLE_TITLE_SIGNALS` word |
| `seniority_fit_score` | +20 | text contains a `JUNIOR_SIGNALS` term |
| `remote_fit_score` | +15 | `remote_type` is remote/hybrid, or remote/hybrid/homeoffice keywords present |
| `skill_fit_score` | +15 | `AUTOMATION_SKILLS` present |
| `skill_fit_score` | +15 | `AI_SKILLS` present |
| `geography_fit_score` | +10 | `region` in {dach, europe, worldwide} or "remote europe" |
| `geography_fit_score` | +5 | `language` in {de, en, ru} |
| `company_fit_score` | +10 | `STARTUP_SIGNALS` present or `is_startup_likely` |
| `compensation_fit_score` | +8 | salary target met |
| `compensation_fit_score` | +7 | weekly-hours target met |

**Penalties** (`penalty_score`, negative)

| Points | Trigger |
|---|---|
| −15 / −5 | salary target **not met** / **unknown** |
| −15 / −5 | weekly-hours target **not met** / **unknown** |
| −30 | senior/lead/staff/director signal in the text |
| −20 | senior/lead signal in the **title** |
| −20 | "5+ years" (or 6/7/8/10+) experience |
| −10 | onsite-only and region not in {dach, europe} |
| −10 | QA/test-automation noise without AI/automation relevance |
| −45 | **title gate** — the **title** has no AI/automation signal and isn't a target role (so AI keywords in the *description* alone, e.g. a "Product Support Specialist" at an AI company, can't score high) |
| −20 | off-target role title (`OFF_TARGET_TITLE_SIGNALS`: web developer, devops, account exec, support, …) when not a target title |
| −25 | title isn't in the role-title family at all |
| −100 | clearly unrelated title (`UNRELATED_TITLE_SIGNALS`) → effectively a hard reject |

**Priority bands** (`priority_from_score`): `≥80 urgent`, `≥70 high`, `≥60 medium`, else `low`.

`explain_score()` turns the same signals into the human-readable "Why this job matches" string seen in
exports.

---

## 10. Detection and enrichment modules

Run by `BaseScraper.normalize_job()` ([`scrapers/base_scraper.py`](scrapers/base_scraper.py)) — each
only fills a field if the source left it empty/unknown:

- **Language** — `matching/language_detection.py` (langdetect-based).
- **Seniority** — `matching/seniority_detection.py` (junior/entry vs senior signals).
- **Remote type** — `matching/remote_detection.py` (remote/hybrid/onsite).
- **Region + city + country** — `matching/region_detection.py` using `REGION_KEYWORDS`,
  `COUNTRY_HINTS`, `CITY_HINTS`. Also exposes `is_location_name()`, which prevents place names from
  being mistaken for company names.
- **Skills** — `matching/skills.py` (`extract_skills` over AI + automation + engineering skill lists).
- **Company size** — `matching/company_intel.py` (`extract_company_size`): parses employee counts and
  ranges from the posting text, or conservatively infers from wording (`enterprise` → large,
  `startup` → small, `mid-market` → medium), else `unknown`.
- **Compensation & hours** — `matching/compensation.py` (`analyze_compensation_and_hours`): extracts
  yearly/monthly EUR figures and weekly hours, compares to targets. Targets:
  `YEARLY_MIN_EUR = 50000`, `MONTHLY_MIN_EUR = 4200`, `WEEKLY_HOURS_MAX = 36`. **Conservative by
  design: "unknown" is preferred over inventing a number.**

---

## 11. Filtering: dedup, company size, min-score

**Deduplication** — `matching/deduplication.py`. A job is a duplicate if any of these collide with a
prior job: normalized URL (tracking params stripped), `deduplication_key`, or a generated signature
(`title without junior/senior/lead/remote/hybrid/gender tokens | company | location`).

**Company size (the < 200 employees rule)** — `matching/company_intel.exceeds_employee_limit()`:

- Reads the lower bound of the detected size label (`"51-200"` → 51, `"1,001+"` → 1001).
- Drops the job only when the company is **known** to exceed the limit (`201-500`, `1,001+`, `200+`,
  enterprise wording, etc.).
- `unknown` or unparseable sizes return `False` → the job is **kept** for manual review, so genuine
  small companies without a published headcount are not lost.
- Threshold via `MAX_COMPANY_EMPLOYEES` (default 200). Applied in `main.py` **and** in
  `export_word_from_excel.py`.

**Min-score** — only `relevance_score >= --min-score` jobs are exported (all scored jobs are still
written to SQLite).

---

## 12. Tests

Run with `pytest` (see the temp/cache note in [section 3](#3-quick-start)). Files in `tests/`:

| Test file | Covers |
|---|---|
| `test_scorer.py` | Score breakdown and clamping. |
| `test_mock_source_flow.py` | Full pipeline on mock data; good vs bad jobs score as expected. |
| `test_serpapi_quality_pipeline.py` | Generic-scraper noise rejection, company/title cleanup (incl. German "bei", job-id/CTA/place/department rejection, reference-domain blocking, aggregator→Unknown), parsing→scoring, dedup, Excel-ready fields. **Runs offline** (HTTP is monkeypatched). |
| `test_company_size_filter.py` | `exceeds_employee_limit` table, place-name guard, mock pipeline drops >200-employee company, Excel→Word excludes large companies. |
| `test_compensation.py` | Salary/hours extraction and target logic. |
| `test_deduplication.py` | URL/signature dedup. |
| `test_region_detection.py` | Region/country detection. |
| `test_remote_detection.py` | Remote/hybrid/onsite. |
| `test_seniority_detection.py` | Junior vs senior. |
| `test_language_detection.py` | Language detection. |
| `test_exporters.py` | Excel/Word files are produced; key columns exist. |
| `test_word_from_excel.py` | Excel→Word round-trip honors the `Dismissed?` workflow. |
| `test_generic_search_queries.py` | Query coverage / region term handling. |
| `test_http_client.py` | Shared HTTP client: success path, retry/backoff, `Retry-After`, UA header, robots.txt enforcement, conditional-request 304 caching, circuit breaker. |
| `test_ats_scraper.py` | ATS scraper: slug loading, Greenhouse/Lever/Ashby/Workable mapping, title relevance filter, scoring flow. |
| `test_hackernews_scraper.py` | HN scraper: picks the "Who is hiring" thread, parses postings, filters noise, company/location/role cleanup. |
| `test_rss_scraper.py` | Generic RSS scraper: company extraction (tag / companyName / "Company: Role"), German-colon guard, agent/ML relevance. |
| `test_discover.py` | ATS discovery: slug extraction per provider, invalid-slug rejection, aggregation, companies.yaml merge. |
| `test_render.py` | Opt-in Playwright JS rendering: disabled raises, enabled returns rendered HTML (mocked). |
| `test_cached_scraper.py` | Cached source replays captured SerpAPI responses offline; rejects aggregator noise. |
| `test_scraper_quality.py` | Relevance pre-filter (AI/tool signals), text sanitizer, RemoteOK/Arbeitnow filtering, WeWorkRemotely RSS parsing. |

Tests import top-level modules (`config`, `database.models`, …), so run them from inside the project
folder. Network is never required — API sources are not hit in tests; the search scraper is mocked.

---

## 13. Optimizations and design decisions already made

- **Conservative compensation parsing** — never fabricates salary/hours; "unknown" is a first-class
  state that only mildly penalizes.
- **Strong noise rejection in the search scraper** — `blocked_domains` (now incl. dictionary, movie,
  and streaming sites that match single words like "junior"), `weak_aggregator_domains`, noisy
  title/path patterns, and a "number-prefixed listicle" filter keep out social profiles, salary
  guides, reference pages, and aggregator spam.
- **Robust company extraction** — handles English "at X", German "bei X", and "@ X"; aggregator/job-board
  domains return `Unknown` instead of a board name; numeric job ids, call-to-action phrases
  ("Jetzt bewerben!"), departments, and place names are never used as a company.
- **Place names are never companies** — `is_location_name()` + domain-token guards stop bugs like
  "Egypt" appearing as a company.
- **SerpAPI-frugal iteration** — `SERPAPI_CAPTURE_DIR` saves raw responses once so parsing can be
  reviewed and improved offline without spending more credits.
- **Multi-key dedup** — URL + key + fuzzy signature catches the same role reposted across boards.
- **Idempotent storage** — SQLite upsert on `deduplication_key`; re-runs update instead of duplicating.
- **Excel as the source of truth** — review in Excel, then regenerate Word from your edits.
- **< 200-employee focus** — applied before storage and in the Excel→Word path.
- **Offline-testable** — `mock` source + monkeypatched HTTP make the whole pipeline CI-friendly.
- **Relevance pre-filter on broad feeds** — `matching/relevance.py` keeps only postings with a real
  AI/agent signal or specific no-code/workflow-automation tooling, so RemoteOK/Arbeitnow/RSS budget is
  not wasted on DevOps/marketing noise (generic "automation" alone does not qualify).
- **Text sanitizer** — `clean_field()` strips upstream-corrupted characters (U+FFFD, stray control
  bytes) so garbled symbols never reach the exports.
- **Feeds over blocked HTML** — We Work Remotely is read via its RSS feed instead of the 403 search page.
- **Polite by construction** — the shared HTTP client honors robots.txt, sends conditional requests
  (ETag/Last-Modified → 304 reuse), and trips a per-host circuit breaker after repeated failures, on
  top of per-host rate limiting, jittered backoff, and a rotating User-Agent pool. robots.txt governs
  crawling, not documented/authenticated APIs, so API calls pass `bypass_robots=True` (e.g. SerpAPI's
  robots disallows `/search.json` for crawlers); HTML page crawling still respects robots.

---

## 14. How to customize this for YOUR job search

This project is meant to be forked and retargeted. The most common changes and exactly where to make
them:

| I want to… | Edit |
|---|---|
| Change the **target job titles** | `matching/keywords.py` → `TARGET_TITLES` (and `ROLE_TITLE_SIGNALS`). |
| Target a **different seniority** | `matching/keywords.py` → `JUNIOR_SIGNALS` / `SENIOR_NEGATIVE_SIGNALS`; weights in `matching/scorer.py`. |
| Change the **skills** that matter | `matching/keywords.py` → `AI_SKILLS`, `AUTOMATION_SKILLS`; `matching/skills.py` → `ENGINEERING_SKILLS`. |
| Add titles to **hard-reject** | `matching/keywords.py` → `UNRELATED_TITLE_SIGNALS`. |
| Change **salary / hours targets** | `matching/compensation.py` → `YEARLY_MIN_EUR`, `MONTHLY_MIN_EUR`, `WEEKLY_HOURS_MAX`. |
| Re-tune **scoring weights / penalties** | `matching/scorer.py` → `calculate_score_breakdown()`. |
| Change **priority thresholds** | `matching/scorer.py` → `priority_from_score()`. |
| Change the **company-size limit** | `.env` → `MAX_COMPANY_EMPLOYEES` (no code change). |
| Track **specific companies** (no SerpAPI) | Add their Greenhouse/Lever slugs to `companies.yaml`, then run `--sources ats`. |
| Adjust **regions / cities / countries** | `matching/keywords.py` → `REGION_KEYWORDS`; `matching/region_detection.py` → `COUNTRY_HINTS`, `CITY_HINTS`. |
| Change **exported columns** | `exporters/xlsx_exporter.py` → `XLSX_COLUMNS`; `exporters/job_presenter.py` → `build_job_record`. |
| Add a **new source** | Create `scrapers/<name>_scraper.py` subclassing `BaseScraper`, implement `search()`, map raw data to `Job`, call `self.normalize_job(job)`, then register it in `SCRAPER_REGISTRY` in `main.py`. |

After any behaviour change: run `pytest`, and **update this guide and the README**.

---

## 15. Roadmap and where to extend

- **Self-built scraper without SerpAPI** — the full plan lives in
  [`SCRAPER_ROADMAP.md`](SCRAPER_ROADMAP.md). **All phases are now implemented:** Phase 0 shared polite
  HTTP client, Phase 1 ATS scraper (Greenhouse + Lever + Ashby + Workable), Phase 2 feeds (We Work
  Remotely RSS, Hacker News "Who is hiring", generic RSS), Phase 3 politeness hardening (robots.txt,
  conditional caching, circuit breaker), Phase 4 SerpAPI discovery loop (`discover_ats_companies.py`),
  and Phase 5 opt-in Playwright rendering (`scrapers/render.py`).
- **Richer company intel** — a real headcount lookup would make the < 200-employee rule fire far more
  often, which matters most for the discovery-loop companies (today most postings have unknown size and
  are kept by design).
- **Bing/Google search parsing** — keys are recognized but parsing is unimplemented.
- **Implement the placeholder sources** (YC, Wellfound, JOIN, …) via official APIs / approved feeds.

---

*Keep this document honest and current. If code and this guide disagree, the code wins — and the guide
should be fixed in the same change.*
