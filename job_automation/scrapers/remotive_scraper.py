from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from database.models import Job
from matching.keywords import TARGET_TITLES
from scrapers.base_scraper import BaseScraper


class RemotiveScraper(BaseScraper):
    source_name = "remotive"
    base_url = "https://remotive.com/api/remote-jobs"

    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        queries = [
            "ai automation",
            "llm",
            "ai agent",
            "workflow automation",
            "no-code automation",
            "solutions engineer ai",
            "applied ai",
            "n8n",
            "zapier",
            "make.com",
        ]
        jobs: list[Job] = []
        seen: set[str] = set()
        for query in queries:
            try:
                response = self.get(f"{self.base_url}?search={quote_plus(query)}")
                payload = response.json()
            except Exception as error:
                self.handle_errors(error)
                continue
            for item in payload.get("jobs", []):
                job = self.parse_job(item)
                if job.job_url in seen:
                    continue
                seen.add(job.job_url)
                jobs.append(self.normalize_job(job))
                if len(jobs) >= self.limit:
                    return jobs
        return jobs

    def parse_job(self, raw_job: dict[str, Any]) -> Job:
        tags = raw_job.get("tags") or []
        description = BeautifulSoup(str(raw_job.get("description") or ""), "lxml").get_text(" ", strip=True)
        return Job(
            job_title=str(raw_job.get("title") or ""),
            company_name=str(raw_job.get("company_name") or ""),
            location=str(raw_job.get("candidate_required_location") or "Remote"),
            remote_type="remote",
            region="worldwide",
            source_platform=self.source_name,
            job_url=str(raw_job.get("url") or ""),
            date_posted=str(raw_job.get("publication_date") or ""),
            job_description=description,
            required_skills=", ".join(str(tag) for tag in tags),
            salary=str(raw_job.get("salary") or ""),
            is_startup_likely=any(term in description.lower() for term in ["startup", "early-stage", "saas", "yc"]),
        )
