# Jobcraw

**Jobcraw is a job crawler made for my specific metrics and job preferences.**

It searches the public web and job APIs for **junior AI-automation / applied-AI /
LLM / workflow-automation roles**, scores every posting from 0–100 against my
criteria, filters out everything I don't want, and exports a clean, ready-to-review
Excel (plus optional Word/CSV).

> 📄 **Looking for the deep technical details?** A full, AI-friendly reference lives
> in **[AIREADME.md](AIREADME.md)** — it documents the architecture, every source,
> the exact scoring, all filters, and how to retarget the tool. This README is the
> short human overview; AIREADME.md is the complete manual.

---

## What it does

1. **Collects** public job postings from many free sources (web search + job APIs/feeds).
2. **Normalizes** each posting — language, seniority, remote type, region, city/country, skills.
3. **Deduplicates** near-identical listings across sources.
4. **Scores** each job 0–100 against my target roles, skills, seniority, region and pay.
5. **Filters** out everything off-target (see below).
6. **Exports** a polished Excel workbook (with score breakdown + a review workflow), and optionally Word/CSV.

## Why it's opinionated (the filters)

Jobcraw is tuned to *my* preferences, so it deliberately drops a lot:

- 🏢 **Small teams only** — companies known to have **more than ~200 employees** are removed (HP, IBM, SAP, ByteDance/TikTok, … are blacklisted by headcount).
- 🚫 **No low-wage-region listings** — postings that pay in PKR/INR/BDT/NGN/… or are based in India, Pakistan, Bangladesh, the Philippines, Vietnam, Nigeria, Egypt, etc. are banned (even a "remote EU" role that secretly pays in rupees).
- 📰 **No noise** — blog posts, tutorials, `*magazine*` articles, GitHub repos and docs pages are rejected; aggregator brands (Indeed, ZipRecruiter, …) never show up as the "company".
- 📍 **Real locations** — the Location column shows an actual place; "Remote/Hybrid" stays in its own column, and unknown places are marked `Unknown`.
- 🔗 **Working links** — result URLs are cleaned and dead links (404/410) are dropped.

## Free by default

The default run uses a **100 % free stack** (DuckDuckGo + Brave free tier + public
job APIs/feeds) — **no paid API key required**. SerpAPI is optional. A built-in
monthly usage counter blocks any metered provider at 95 % of its quota so you never
get a surprise bill.

## Quickstart

> The code lives in the **`job_automation/`** folder.

```bash
cd job_automation
python -m venv .venv
.venv\Scripts\activate            # Windows (use: source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
copy .env.example .env            # then optionally add API keys; the free stack needs none
pip install ddgs                  # enables the free DuckDuckGo search backend
```

Run a search and get an Excel:

```bash
python main.py --region europe --min-score 60 --export xlsx
```

A bigger worldwide sweep into one workbook:

```bash
python main.py --region worldwide --min-score 60 --limit 50 --export xlsx
```

Exports land in `job_automation/data/exports/`.

## Project structure

```
.
├── README.md            ← you are here (human overview)
├── AIREADME.md          ← full technical / AI reference
└── job_automation/      ← the application
    ├── main.py                  # CLI entry point
    ├── scrapers/                # web-search + API/feed sources
    ├── matching/                # scoring, dedup, filters, bans
    ├── exporters/               # Excel / Word / CSV
    ├── company_sizes.yaml       # large-company blacklist
    ├── targeting.yaml           # tune titles / regions / search terms
    ├── PROJECT_GUIDE.md         # architecture & customization guide
    ├── SCRAPER_ROADMAP.md       # crawler roadmap
    └── SCHEDULING.md            # run it daily, get only new postings
```

## Configuration & secrets

- Copy `job_automation/.env.example` → `job_automation/.env` and put any API keys there.
- **`.env` is git-ignored** — your keys are never committed. Only the empty `.env.example` template is in the repo.

## Ethics

Jobcraw avoids scraping login/captcha-protected platforms (LinkedIn, Indeed,
Glassdoor, …). It prefers official APIs, allowed feeds, search APIs and
robots-respecting reads of public structured data.

---

*For everything else — sources, scoring math, every filter, retargeting, tests,
troubleshooting — see **[AIREADME.md](AIREADME.md)**.*
