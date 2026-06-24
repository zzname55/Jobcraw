from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from database.models import Job
from matching.relevance import is_relevant_text
from scrapers.base_scraper import BaseScraper


class RemoteOKScraper(BaseScraper):
    source_name = "remoteok"
    base_url = "https://remoteok.com"

    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        try:
            response = self.get(f"{self.base_url}/api")
            payload = response.json()
        except Exception as error:
            self.handle_errors(error)
            return []

        jobs: list[Job] = []
        for item in payload:
            if not isinstance(item, dict) or "position" not in item:
                continue
            job = self.parse_job(item)
            # RemoteOK's /api returns the whole board; keep only AI/automation roles.
            if not is_relevant_text(job.text_blob()):
                continue
            jobs.append(self.normalize_job(job))
            if len(jobs) >= self.limit:
                break
        return jobs

    def parse_job(self, raw_job: dict[str, Any]) -> Job:
        tags = raw_job.get("tags") or []
        description = " ".join(str(tag) for tag in tags)
        return Job(
            job_title=str(raw_job.get("position") or ""),
            company_name=str(raw_job.get("company") or ""),
            location=str(raw_job.get("location") or "Remote"),
            remote_type="remote",
            region="worldwide",
            source_platform=self.source_name,
            job_url=str(raw_job.get("url") or raw_job.get("apply_url") or ""),
            date_posted=str(raw_job.get("date") or ""),
            job_description=BeautifulSoup(str(raw_job.get("description") or description), "lxml").get_text(" ", strip=True),
            required_skills=", ".join(str(tag) for tag in tags),
            salary=self._format_salary(raw_job),
        )

    def _format_salary(self, raw_job: dict[str, Any]) -> str:
        salary = raw_job.get("salary")
        if salary:
            return str(salary)
        salary_min = int(raw_job.get("salary_min") or 0)
        salary_max = int(raw_job.get("salary_max") or 0)
        if salary_min and salary_max:
            return f"{salary_min}-{salary_max}"
        if salary_min:
            return f"{salary_min}+"
        return ""
