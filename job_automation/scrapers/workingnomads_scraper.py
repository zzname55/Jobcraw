from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from database.models import Job
from matching.relevance import is_relevant_text
from scrapers.base_scraper import BaseScraper


class WorkingNomadsScraper(BaseScraper):
    """Key-free remote-jobs source via the public Working Nomads JSON feed.

    Working Nomads exposes its full live board at a single JSON endpoint
    (``/api/exposed_jobs/``) and its robots.txt allows everything, so this is a
    polite, no-key way to add more remote AI/automation coverage. The board is
    broad, so each posting is filtered on its title with the shared relevance
    pre-filter before it enters the pipeline.
    """

    source_name = "workingnomads"
    source_type = "feed"
    base_url = "https://www.workingnomads.com"
    feed_url = "https://www.workingnomads.com/api/exposed_jobs/"

    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        try:
            response = self.get(self.feed_url)
            items = response.json()
        except Exception as error:
            self.handle_errors(error)
            return []
        if not isinstance(items, list):
            return []

        jobs: list[Job] = []
        for item in items:
            job = self._parse_item(item)
            if job is None:
                continue
            jobs.append(self.normalize_job(job))
            if len(jobs) >= self.limit:
                break
        return jobs

    def _parse_item(self, item: dict[str, Any]) -> Job | None:
        if not isinstance(item, dict):
            return None
        title = str(item.get("title") or "").strip()
        # Match on the title only: full descriptions are noisy marketing copy that
        # frequently mention "AI", which would let unrelated roles slip through.
        if not title or not is_relevant_text(title):
            return None
        description_html = str(item.get("description") or "")
        description = BeautifulSoup(description_html, "lxml").get_text(" ", strip=True) if description_html else ""
        tags = item.get("tags")
        skills = ", ".join(tags) if isinstance(tags, list) else str(tags or "")
        return Job(
            job_title=title[:160],
            company_name=str(item.get("company_name") or "Unknown").strip()[:80] or "Unknown",
            location=str(item.get("location") or "Remote").strip() or "Remote",
            remote_type="remote",
            source_platform="workingnomads",
            source_type=self.source_type,
            job_url=str(item.get("url") or ""),
            date_posted=str(item.get("pub_date") or ""),
            job_description=description,
            required_skills=skills[:300],
        )
