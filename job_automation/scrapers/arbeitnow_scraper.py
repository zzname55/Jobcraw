from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from database.models import Job
from matching.relevance import is_relevant_text
from scrapers.base_scraper import BaseScraper


class ArbeitnowScraper(BaseScraper):
    source_name = "arbeitnow"
    base_url = "https://www.arbeitnow.com/api/job-board-api"

    def search(self, region: str = "europe", remote: bool = True) -> list[Job]:
        jobs: list[Job] = []
        page = 1
        # Arbeitnow returns a general board; scan more pages but keep only relevant
        # AI/automation roles so the per-source budget is not wasted on noise.
        while len(jobs) < self.limit and page <= 5:
            try:
                response = self.get(self.base_url, params={"page": page})
                payload = response.json()
            except Exception as error:
                self.handle_errors(error)
                break
            data = payload.get("data", [])
            if not data:
                break
            for item in data:
                job = self.parse_job(item)
                if not is_relevant_text(job.text_blob()):
                    continue
                jobs.append(self.normalize_job(job))
                if len(jobs) >= self.limit:
                    break
            page += 1
        return jobs

    def parse_job(self, raw_job: dict[str, Any]) -> Job:
        description = BeautifulSoup(str(raw_job.get("description") or ""), "lxml").get_text(" ", strip=True)
        tags = raw_job.get("tags") or []
        location = str(raw_job.get("location") or "")
        return Job(
            job_title=str(raw_job.get("title") or ""),
            company_name=str(raw_job.get("company_name") or ""),
            location=location,
            remote_type="remote" if raw_job.get("remote") else "unknown",
            region="europe",
            country="germany" if "germany" in location.lower() or "berlin" in location.lower() else "",
            source_platform=self.source_name,
            job_url=str(raw_job.get("url") or ""),
            date_posted=str(raw_job.get("created_at") or ""),
            job_description=description,
            required_skills=", ".join(str(tag) for tag in tags),
        )
