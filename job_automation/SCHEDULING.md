# Scheduling the scraper (daily, new postings only)

The scraper is designed to run unattended on a schedule and show you **only what's
new**. Every run stores all scored jobs in SQLite (`jobs.db`); with `--new-only true`
the export contains just the postings that weren't in the database before this run.
The default sources are all free and key-free, so no secrets are required.

The exact command the schedulers run:

```bash
python main.py --region europe --remote true --min-score 60 --new-only true --export all
```

`--export all` writes CSV + Excel + Word into `data/exports/`, and also pushes to
Notion / Google Sheets if those are enabled in `.env`.

## Windows (Task Scheduler)

A ready-made wrapper lives at [`scripts/run_daily.ps1`](scripts/run_daily.ps1). Register
it to run daily at 08:00 (run from the `job_automation` folder):

```bat
schtasks /Create /SC DAILY /TN "AI Job Scrape" /ST 08:00 ^
  /TR "powershell -NoProfile -ExecutionPolicy Bypass -File \"%CD%\scripts\run_daily.ps1\""
```

Check it ran: **Task Scheduler → Task Scheduler Library → "AI Job Scrape"**, or look at
the newest file in `data/exports/`. Remove it with `schtasks /Delete /TN "AI Job Scrape" /F`.

## Linux / macOS (cron)

Use [`scripts/run_daily.sh`](scripts/run_daily.sh):

```cron
0 8 * * * /path/to/job_automation/scripts/run_daily.sh >> /path/to/job_automation/data/logs/cron.log 2>&1
```

## GitHub Actions (no machine kept on)

[`.github/workflows/daily-jobs.yml`](../.github/workflows/daily-jobs.yml) runs the scrape
every day at 06:00 UTC (and on demand via **Actions → Daily job scrape → Run workflow**).
It caches `jobs.db` + `data/http_cache.json` between runs so `--new-only` works across days,
and uploads the exports as a downloadable **job-exports** artifact.

Optional repo secrets:

| Secret | Effect |
|---|---|
| `BRAVE_SEARCH_API_KEY` | Enables the Brave search backend (free tier ~2000/month). |
| `NOTION_API_KEY`, `NOTION_DATABASE_ID` | Pushes new hits into a Notion database. |

## Getting the new hits delivered

`--export all` already populates Notion / Google Sheets when enabled, which is the
simplest "inbox". For email, point Task Scheduler/cron at a tiny follow-up step that mails
the newest file in `data/exports/`, or read the GitHub Actions artifact. (An SMTP exporter
is a natural next addition if you want email built in.)
