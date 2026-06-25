"""Dev tool: compare the paid SerpAPI scraper vs the free scraper stack.

Runs each source set through the same scoring/dedup/<200-employee pipeline,
exports a named Excel per side, and prints a metrics table plus the company
overlap. SerpAPI responses are captured so the spent credits are reusable.

Usage: .venv/Scripts/python.exe compare_runs.py
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

os.environ.setdefault("SERPAPI_CAPTURE_DIR", "data/serpapi_capture")
os.environ.setdefault("SERPAPI_FETCH_DETAILS", "false")

import logging

logging.disable(logging.WARNING)

from config import MAX_COMPANY_EMPLOYEES  # noqa: E402
from database.models import Job  # noqa: E402
from matching.company_intel import exceeds_employee_limit  # noqa: E402
from matching.deduplication import deduplicate_jobs  # noqa: E402
from exporters.xlsx_exporter import export_jobs_to_xlsx  # noqa: E402
from main import score_jobs  # noqa: E402
from scrapers.generic_search_scraper import CachedSearchScraper, DuckDuckGoSearchScraper, GenericSearchScraper  # noqa: E402
from scrapers.join_scraper import JoinScraper  # noqa: E402
from scrapers.workingnomads_scraper import WorkingNomadsScraper  # noqa: E402
from scrapers.remoteok_scraper import RemoteOKScraper  # noqa: E402
from scrapers.remotive_scraper import RemotiveScraper  # noqa: E402
from scrapers.arbeitnow_scraper import ArbeitnowScraper  # noqa: E402

REGION = "europe"
TARGET_HINTS = ["ai automation", "automation specialist", "ai agent", "workflow automation", "n8n", "ai engineer", "llm"]
DACH_HINTS = ["german", "deutschland", "berlin", "munich", "münchen", "hamburg", "vienna", "wien", "zurich", "zürich", "dach", "austria", "switzerland"]


def export_named(jobs: list[Job], name: str) -> None:
    path = export_jobs_to_xlsx(jobs)
    target = Path("data/exports") / name
    shutil.copyfile(path, target)
    print(f"  exported {len(jobs)} -> {target}")


def run(scrapers) -> list[Job]:
    raw: list[Job] = []
    for scraper in scrapers:
        try:
            jobs = scraper.search(region=REGION, remote=True)
            print(f"  {scraper.source_name}: {len(jobs)}")
            raw.extend(jobs)
        except Exception as error:  # noqa: BLE001
            print(f"  {scraper.source_name}: FAILED {error}")
    unique = deduplicate_jobs(raw)
    scored = sorted(score_jobs(unique), key=lambda j: j.relevance_score, reverse=True)
    kept = [j for j in scored if not exceeds_employee_limit(j.company_size, MAX_COMPANY_EMPLOYEES)]
    return raw, kept


def metrics(name: str, raw: list[Job], kept: list[Job]) -> dict:
    ge50 = [j for j in kept if j.relevance_score >= 50]
    ge60 = [j for j in kept if j.relevance_score >= 60]
    ge80 = [j for j in kept if j.relevance_score >= 80]
    targets = [j for j in ge50 if any(h in j.job_title.lower() for h in TARGET_HINTS)]
    dach = [j for j in ge50 if any(h in (j.job_title + " " + j.location + " " + j.country).lower() for h in DACH_HINTS)]
    companies = {j.company_name for j in ge50 if j.company_name and j.company_name != "Unknown"}
    unknown = sum(1 for j in ge50 if j.company_name in ("", "Unknown"))
    return {
        "name": name,
        "raw": len(raw),
        "kept": len(kept),
        ">=50": len(ge50),
        ">=60": len(ge60),
        ">=80": len(ge80),
        "target_hits": len(targets),
        "dach_hits": len(dach),
        "uniq_companies": len(companies),
        "unknown_company": unknown,
        "companies": companies,
        "ge50": ge50,
    }


def main() -> None:
    replay = os.getenv("SERPAPI_REPLAY") == "1"
    print(f"=== SerpAPI ({'cached replay' if replay else '20 live searches'}) ===")
    serp_scraper = CachedSearchScraper(limit=60) if replay else GenericSearchScraper(limit=20)
    serp_raw, serp_kept = run([serp_scraper])
    export_named([j for j in serp_kept if j.relevance_score >= 50], "COMPARE_serpapi.xlsx")

    print("=== Free stack ===")
    free_raw, free_kept = run([
        DuckDuckGoSearchScraper(limit=20),
        JoinScraper(limit=15),
        WorkingNomadsScraper(limit=25),
        RemoteOKScraper(limit=25),
        RemotiveScraper(limit=25),
        ArbeitnowScraper(limit=25),
    ])
    export_named([j for j in free_kept if j.relevance_score >= 50], "COMPARE_own.xlsx")

    m_serp = metrics("SerpAPI", serp_raw, serp_kept)
    m_free = metrics("Free", free_raw, free_kept)

    cols = ["raw", "kept", ">=50", ">=60", ">=80", "target_hits", "dach_hits", "uniq_companies", "unknown_company"]
    print("\n=== METRICS ===")
    print(f"{'metric':16} {'SerpAPI':>10} {'Free':>10}")
    for c in cols:
        print(f"{c:16} {m_serp[c]:>10} {m_free[c]:>10}")

    overlap = m_serp["companies"] & m_free["companies"]
    print(f"\ncompany overlap (>=50): {len(overlap)} -> {sorted(overlap)[:15]}")
    print(f"SerpAPI-only companies: {sorted(m_serp['companies'] - m_free['companies'])[:15]}")
    print(f"Free-only companies:    {sorted(m_free['companies'] - m_serp['companies'])[:15]}")

    def ascii(value: str) -> str:
        return (value or "").encode("ascii", "ignore").decode("ascii")

    print("\n=== Free top 12 (>=50) ===")
    for j in m_free["ge50"][:12]:
        print(f"  {j.relevance_score:3} [{ascii(j.company_name)[:24]:24}] {ascii(j.job_title)[:46]:46} | {ascii(j.location)[:18]} | {ascii(j.source_platform)[:18]}")


if __name__ == "__main__":
    main()
