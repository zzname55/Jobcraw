# AI Job Automation

Python MVP for discovering and ranking junior roles in AI automation, applied AI, AI agents, LLM automation, no-code automation, workflow automation, and AI solutions.

The project collects public job postings, normalizes them, detects language/seniority/remote type/region, deduplicates records, scores jobs from 0 to 100, stores them in SQLite, and exports readable job lists.

**Only companies with fewer than 200 employees are targeted.** Postings from companies that are known to exceed 200 employees are dropped before scoring and export, so the focus stays on startups and small/mid-size teams. See [Company Size Filter](#company-size-filter).

## Documentation

- **[PROJECT_GUIDE.md](PROJECT_GUIDE.md)** — the full reference: architecture, sources/APIs, input/output, exact scoring metrics, detection, filters, tests, and **how to customize this for your own job search**. Read this first if you want to change anything (it is written so an AI assistant can explain the system to you).
- **[SCRAPER_ROADMAP.md](SCRAPER_ROADMAP.md)** — the plan for making the self-built crawler strong and reliable, and for switching between SerpAPI and a key-free crawler.

## Installation

Requirement: Python 3.11+

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Optional browser automation setup:

```bash
playwright install
```

## Run The Automation

```bash
python main.py --region europe --remote true --min-score 60 --export xlsx
python main.py --region dach --remote true --min-score 70 --sources remoteok,remotive,arbeitnow,generic --export all
python main.py --region worldwide --remote true --min-score 80 --export docx
```

Exports are saved in `data/exports/`.

Export modes:

```bash
python main.py --region europe --remote true --min-score 60 --export xlsx
python main.py --region europe --remote true --min-score 60 --export docx
python main.py --region europe --remote true --min-score 60 --export all
```

- `xlsx` creates a polished Excel workbook with an overview, detailed job table, score breakdown, city/country fields, company size, status fields, notes, and dismissal workflow.
- `docx` creates a readable Word report with job cards.
- `csv` creates a raw CSV export.
- `all` creates CSV, Excel, and Word together.

## Generate Word From Edited Excel

Use Excel as the source of truth. Mark rows in the `Dismissed?` column as `yes` or `no`, then regenerate Word from the edited workbook:

```bash
python export_word_from_excel.py
python export_word_from_excel.py --include-dismissed false
python export_word_from_excel.py --include-dismissed true
python export_word_from_excel.py --excel data/exports/jobs_export_2026-06-24_pretty.xlsx
```

By default dismissed rows and rows with `Status = dismissed` are excluded from the Word report. Rows whose `Company Size` is above 200 employees are also excluded, matching the [Company Size Filter](#company-size-filter).

## Dashboard

```bash
streamlit run dashboard/app.py
```

The dashboard shows sorted jobs, filters for region/country/remote type/seniority/language/source/priority, CSV download, and status updates.

## Active Sources

Implemented sources:

- RemoteOK via public API
- Remotive via public API
- Arbeitnow via public API
- We Work Remotely via public RSS feed
- Generic Search via SerpAPI when `SERPAPI_API_KEY` is set
- ATS boards (Greenhouse + Lever + Ashby + Workable) via `--sources ats`, key-free; list company slugs in `companies.yaml`
- Hacker News "Ask HN: Who is hiring?" monthly thread via `--sources hackernews`, key-free
- RSS/Atom job feeds via `--sources rss`, key-free; configurable with `RSS_FEEDS`
- Manual import via `manual_jobs.csv`
- Mock source for offline testing via `--sources mock`

Defensive placeholders:

- YC Jobs
- Wellfound
- JOIN
- GermanTechJobs
- BerlinStartupJobs

Direct scraping of platforms such as LinkedIn, Indeed, Glassdoor, and login/captcha-protected job boards should be avoided. Prefer official APIs, allowed feeds, search APIs, sitemaps, or manual imports.

## SerpAPI

Put your key in `.env`:

```env
SERPAPI_API_KEY=your_key_here
```

Each generated query consumes one SerpAPI search credit. The generic search source also tries to fetch concrete job-detail pages for better descriptions, skills, salary, and hours extraction. Start small, for example:

```bash
python main.py --sources generic --limit 20 --region europe --remote true --min-score 50 --export all
```

### Discover ATS companies (frugal SerpAPI use)

Instead of spending credits on individual jobs, spend a few on discovering company ATS boards, then
fetch their jobs for free forever via `--sources ats`:

```bash
python discover_ats_companies.py --limit 12   # ~12 credits -> ~100 company slugs in companies.yaml
python main.py --sources ats --min-score 60 --export xlsx
```

Discovery cannot know company size, so prune large companies from `companies.yaml` by hand.

## Company Size Filter

This tool intentionally targets **only companies with fewer than 200 employees** (startups and small/mid-size teams).

- Company size is read from the posting text (for example `"team of 40"`, `"51-200 employees"`) or conservatively inferred from wording such as `enterprise`, `startup`, or `mid-market`.
- A posting is dropped before scoring and export whenever the detected size is clearly above 200 employees (for example `201-500`, `1,001+`, or `enterprise` wording).
- When the size cannot be determined it is marked `unknown` and the posting is **kept** for manual review, so genuine small companies without a published headcount are not lost.
- The filter also applies when a Word report is generated from an edited Excel workbook: rows whose `Company Size` exceeds 200 are excluded.
- The threshold can be changed with the `MAX_COMPANY_EMPLOYEES` environment variable (default `200`).

## Scoring

Scores are capped between 0 and 100.

Excel includes separate score columns so you can audit why a role ranked highly:

- `Title Fit`: target title and target role family signals.
- `Seniority Fit`: junior, entry-level, trainee, intern, or early-career signals.
- `Remote Fit`: remote, hybrid, home-office, or distributed-work signals.
- `Skill Fit`: AI, LLM, agents, workflow automation, no-code/low-code, APIs, n8n, MCP, and related skills.
- `Geo Fit`: DACH, Europe, worldwide remote, and supported language signals.
- `Comp / Hours Fit`: salary target and 36h/week target signals when visible.
- `Company Signal Fit`: startup, SaaS, B2B, GTM, RevOps, or similar context.
- `Penalty`: seniority, unrelated title, QA-only automation, onsite mismatch, weak role fit, missing salary, or missing hours penalties.

Important negative signals:

- `-30` senior/lead/staff/director signals in the posting
- `-20` senior/lead signal in the title
- `-20` more than 5 years of experience
- `-10` onsite-only outside target regions
- `-10` QA/test automation noise without AI/workflow relevance
- `-45` title gate: the title has no AI/automation signal and is not a target role (AI keywords in the description alone do not qualify)
- `-20` off-target role title (web developer, devops, account executive, support, ...) unless it is a target title
- `-25` title does not look like a target role family
- `0` hard reject for clearly unrelated titles such as graphic designer, admin support, or customer support

## Excel Review Workflow

Use Excel as the source of truth:

- `Status`: `new`, `shortlist`, `applied`, `interview`, or `dismissed`.
- `City` / `Country`: extracted from the posting text, location, and known city hints.
- `Company Size`: extracted from employee-count text when available, otherwise conservatively inferred or marked `unknown`. Companies known to have more than 200 employees are filtered out (see [Company Size Filter](#company-size-filter)).
- `Interesting?`: optional manual yes/no marker.
- `Applied?`: optional manual yes/no marker.
- `Next Step`: your next action, for example "apply", "research salary", or "ask recruiter".
- `Review Notes`: your manual notes.
- `Dismissed?`: set to `yes` to gray out and strike through the row.

Priority levels:

- 80-100: urgent
- 70-79: high
- 60-69: medium
- 0-59: low

## Add A New Source

1. Add a file in `scrapers/`.
2. Inherit from `BaseScraper`.
3. Implement `source_name`, `base_url`, and `search()`.
4. Map raw data into `Job` and call `normalize_job(job)`.
5. Register the source in `SCRAPER_REGISTRY` in `main.py`.

## Tests

```bash
pytest
```

## Troubleshooting

- If Generic Search returns no jobs, check `SERPAPI_API_KEY` in `.env`.
- If no export is created, check `--min-score`; jobs below that score are filtered out.
- If one source fails, the error is logged and the next source continues.
- Logs are stored in `data/logs/job_automation.log`.
