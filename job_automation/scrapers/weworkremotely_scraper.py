from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from database.models import Job
from scrapers.base_scraper import BaseScraper


class WeWorkRemotelyScraper(BaseScraper):
    source_name = "weworkremotely"
    base_url = "https://weworkremotely.com"

    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        try:
            response = self.get(f"{self.base_url}/remote-jobs/search?term=ai+automation")
        except Exception as error:
            self.handle_errors(error)
            return []

        soup = BeautifulSoup(response.text, "lxml")
        jobs: list[Job] = []
        for anchor in soup.select("section.jobs li:not(.view-all) a[href]"):
            href = anchor.get("href", "")
            title = anchor.select_one(".title")
            company = anchor.select_one(".company")
            region_text = anchor.select_one(".region")
            if not title or not company:
                continue
            job = Job(
                job_title=title.get_text(" ", strip=True),
                company_name=company.get_text(" ", strip=True),
                location=region_text.get_text(" ", strip=True) if region_text else "Remote",
                remote_type="remote",
                region="worldwide",
                source_platform=self.source_name,
                job_url=urljoin(self.base_url, href),
                job_description=anchor.get_text(" ", strip=True),
            )
            jobs.append(self.normalize_job(job))
            if len(jobs) >= self.limit:
                break
        return jobs
