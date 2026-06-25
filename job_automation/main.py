from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from config import DB_PATH, DEFAULT_MIN_SCORE, DEFAULT_SOURCES, LOG_DIR, MAX_COMPANY_EMPLOYEES, MAX_JOBS_PER_SOURCE
from database.db import JobDatabase
from database.models import Job
from matching.company_intel import exceeds_employee_limit
from exporters.csv_exporter import export_jobs_to_csv
from exporters.docx_exporter import export_jobs_to_docx
from exporters.google_sheets_exporter import export_to_google_sheets
from exporters.notion_exporter import export_to_notion
from exporters.xlsx_exporter import export_jobs_to_xlsx
from matching.deduplication import deduplicate_jobs, prepare_deduplication
from matching.scorer import apply_score_breakdown, classify_company_fit, explain_score, priority_from_score
from scrapers.berlin_startup_jobs_scraper import BerlinStartupJobsScraper
from scrapers.arbeitnow_scraper import ArbeitnowScraper
from scrapers.ats_scraper import AtsScraper
from scrapers.hackernews_scraper import HackerNewsHiringScraper
from scrapers.rss_scraper import RssFeedScraper
from scrapers.generic_search_scraper import BraveSearchScraper, CachedSearchScraper, DuckDuckGoSearchScraper, GenericSearchScraper
from scrapers.german_tech_jobs_scraper import GermanTechJobsScraper
from scrapers.join_scraper import JoinScraper
from scrapers.manual_source_scraper import ManualSourceScraper
from scrapers.mock_website_scraper import MockWebsiteScraper
from scrapers.remoteok_scraper import RemoteOKScraper
from scrapers.remotive_scraper import RemotiveScraper
from scrapers.weworkremotely_scraper import WeWorkRemotelyScraper
from scrapers.workingnomads_scraper import WorkingNomadsScraper
from scrapers.wellfound_scraper import WellfoundScraper
from scrapers.yc_jobs_scraper import YCJobsScraper


app = typer.Typer(help="Junior AI Automation job scraper and matcher.")
console = Console()


SCRAPER_REGISTRY = {
    "remoteok": RemoteOKScraper,
    "remotive": RemotiveScraper,
    "arbeitnow": ArbeitnowScraper,
    "weworkremotely": WeWorkRemotelyScraper,
    "yc": YCJobsScraper,
    "generic": GenericSearchScraper,
    "cached": CachedSearchScraper,
    "duckduckgo": DuckDuckGoSearchScraper,
    "brave": BraveSearchScraper,
    "ats": AtsScraper,
    "hackernews": HackerNewsHiringScraper,
    "rss": RssFeedScraper,
    "workingnomads": WorkingNomadsScraper,
    "mock": MockWebsiteScraper,
    "manual": ManualSourceScraper,
    "join": JoinScraper,
    "germantechjobs": GermanTechJobsScraper,
    "berlinstartupjobs": BerlinStartupJobsScraper,
    "wellfound": WellfoundScraper,
}


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "job_automation.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def selected_scrapers(source_names: str | None, limit: int):
    names = [name.strip().lower() for name in source_names.split(",")] if source_names else list(DEFAULT_SOURCES)
    scrapers = []
    for name in names:
        scraper_class = SCRAPER_REGISTRY.get(name)
        if not scraper_class:
            console.print(f"[yellow]Unknown source skipped:[/] {name}")
            continue
        scrapers.append(scraper_class(limit=limit))
    return scrapers


def score_jobs(jobs: list[Job]) -> list[Job]:
    scored_jobs: list[Job] = []
    for job in jobs:
        prepare_deduplication(job)
        apply_score_breakdown(job)
        job.company_fit = classify_company_fit(job)
        job.priority_level = priority_from_score(job.relevance_score)
        job.reason_for_score = explain_score(job)
        scored_jobs.append(job)
    return scored_jobs


def print_top_jobs(jobs: list[Job], count: int = 5) -> None:
    table = Table(title="Top Jobs")
    table.add_column("#")
    table.add_column("Score")
    table.add_column("Title")
    table.add_column("Company")
    table.add_column("Location")
    for index, job in enumerate(jobs[:count], start=1):
        table.add_row(
            str(index),
            str(job.relevance_score),
            _console_safe(job.job_title),
            _console_safe(job.company_name),
            _console_safe(job.location),
        )
    console.print(table)


def _console_safe(value: str, limit: int = 80) -> str:
    safe = (value or "").encode("ascii", errors="ignore").decode("ascii")
    safe = " ".join(safe.split())
    return safe[:limit]


@app.command()
def run(
    region: str = typer.Option("worldwide", help="germany, dach, europe, asia, america, worldwide"),
    remote: str = typer.Option("true", help="true/false"),
    min_score: int = typer.Option(DEFAULT_MIN_SCORE, help="Minimum score for export"),
    export: str = typer.Option("xlsx", help="xlsx / docx / csv / both / all / none"),
    sources: str | None = typer.Option(None, help="Comma separated sources, e.g. remoteok,weworkremotely,yc"),
    limit: int = typer.Option(MAX_JOBS_PER_SOURCE, help="Maximum jobs per source"),
    new_only: str = typer.Option("false", help="Export only postings not seen in a previous run (incremental)"),
    dashboard: str = typer.Option("false", help="true/false"),
) -> None:
    setup_logging()
    remote_only = parse_bool(remote)
    incremental = parse_bool(new_only)
    db = JobDatabase(DB_PATH)
    db.init()
    # Snapshot the 'seen' set BEFORE this run upserts, so we can tell new from old.
    previously_seen = db.existing_keys()

    raw_jobs: list[Job] = []
    for scraper in selected_scrapers(sources, limit):
        try:
            jobs = scraper.search(region=region, remote=remote_only)
            raw_jobs.extend(jobs)
            console.print(f"[green]{scraper.source_name}:[/] {len(jobs)} jobs")
        except Exception as error:
            logging.getLogger(__name__).warning("%s failed: %s", scraper.source_name, error)

    unique_jobs = deduplicate_jobs(raw_jobs)
    all_scored = sorted(score_jobs(unique_jobs), key=lambda job: job.relevance_score, reverse=True)
    scored_jobs = [job for job in all_scored if not exceeds_employee_limit(job.company_size, MAX_COMPANY_EMPLOYEES)]
    removed_large_companies = len(all_scored) - len(scored_jobs)
    new_jobs = [job for job in scored_jobs if job.deduplication_key not in previously_seen]
    db.upsert_jobs(scored_jobs)

    candidate_jobs = new_jobs if incremental else scored_jobs
    exportable_jobs = [job for job in candidate_jobs if job.relevance_score >= min_score]
    export_mode = export.lower()
    csv_path: Path | None = None
    xlsx_path: Path | None = None
    docx_path: Path | None = None
    if export_mode in {"csv", "both", "all"}:
        csv_path = export_jobs_to_csv(exportable_jobs)
    if export_mode in {"xlsx", "excel", "both", "all"}:
        xlsx_path = export_jobs_to_xlsx(exportable_jobs)
    if export_mode in {"docx", "word", "all"}:
        docx_path = export_jobs_to_docx(exportable_jobs)
    export_to_google_sheets(exportable_jobs)
    export_to_notion(exportable_jobs)

    console.print(f"Found {len(raw_jobs)} raw jobs.")
    console.print(f"Removed {len(raw_jobs) - len(unique_jobs)} duplicates.")
    console.print(f"Removed {removed_large_companies} jobs from companies over {MAX_COMPANY_EMPLOYEES} employees.")
    console.print(f"Scored {len(scored_jobs)} jobs.")
    console.print(f"New since last run: {len(new_jobs)} jobs ({len(previously_seen)} already seen).")
    if incremental:
        console.print(f"Exported {len(exportable_jobs)} NEW jobs with score >= {min_score} (incremental mode).")
    else:
        console.print(f"Exported {len(exportable_jobs)} jobs with score >= {min_score}.")
    if csv_path:
        console.print(f"CSV saved to {csv_path}")
    if xlsx_path:
        console.print(f"Excel saved to {xlsx_path}")
    if docx_path:
        console.print(f"Word report saved to {docx_path}")
    print_top_jobs(exportable_jobs)

    if parse_bool(dashboard):
        console.print("Start dashboard with: streamlit run dashboard/app.py")


if __name__ == "__main__":
    typer.run(run)
