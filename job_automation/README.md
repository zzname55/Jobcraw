# Jobcraw — application code

This folder contains the Jobcraw application. The documentation now lives at the
repository root:

- **[../README.md](../README.md)** — short human overview of the project.
- **[../AIREADME.md](../AIREADME.md)** — full technical / AI reference (architecture,
  sources, scoring, all filters, customization, tests, troubleshooting).

Deep-dive docs in this folder:

- **[PROJECT_GUIDE.md](PROJECT_GUIDE.md)** — architecture & how to customize.
- **[SCRAPER_ROADMAP.md](SCRAPER_ROADMAP.md)** — crawler roadmap.
- **[SCHEDULING.md](SCHEDULING.md)** — run it daily, get only new postings.

Quickstart (from this directory):

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python main.py --region europe --min-score 60 --export xlsx
```
