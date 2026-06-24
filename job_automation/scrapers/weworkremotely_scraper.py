from __future__ import annotations

from bs4 import BeautifulSoup

from database.models import Job
from matching.relevance import is_relevant_text
from scrapers.base_scraper import BaseScraper


class WeWorkRemotelyScraper(BaseScraper):
    """We Work Remotely via its public RSS feed.

    The HTML search page returns 403 to non-browser clients, but the RSS feed is
    published for consumption and returns clean, structured items (company/title,
    region, country, skills). This is the polite, unblocked path (roadmap Phase 2).
    """

    source_name = "weworkremotely"
    base_url = "https://weworkremotely.com"
    feed_url = "https://weworkremotely.com/remote-jobs.rss"

    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        try:
            response = self.get(self.feed_url)
        except Exception as error:
            self.handle_errors(error)
            return []

        soup = BeautifulSoup(response.content, "xml")
        jobs: list[Job] = []
        for item in soup.find_all("item"):
            raw_title = self._text(item, "title")
            company, title = self._split_company_title(raw_title)
            location = " ".join(part for part in [self._text(item, "region"), self._text(item, "country")] if part) or "Remote"
            skills = self._text(item, "skills")
            description = BeautifulSoup(self._text(item, "description"), "lxml").get_text(" ", strip=True)

            if not is_relevant_text(f"{title} {skills} {description}"):
                continue

            job = Job(
                job_title=title,
                company_name=company,
                location=location,
                remote_type="remote",
                region="worldwide",
                source_platform=self.source_name,
                job_url=self._text(item, "link"),
                date_posted=self._text(item, "pubDate"),
                job_description=description,
                required_skills=skills,
            )
            jobs.append(self.normalize_job(job))
            if len(jobs) >= self.limit:
                break
        return jobs

    def _text(self, item, tag: str) -> str:
        element = item.find(tag)
        return element.get_text(strip=True) if element else ""

    def _split_company_title(self, raw_title: str) -> tuple[str, str]:
        if ":" in raw_title:
            company, _, title = raw_title.partition(":")
            return company.strip(), title.strip() or raw_title.strip()
        return "", raw_title.strip()
