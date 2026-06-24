from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from config import RSS_FEEDS
from database.models import Job
from matching.relevance import is_relevant_text
from scrapers.base_scraper import BaseScraper


class RssFeedScraper(BaseScraper):
    """Generic RSS/Atom job-feed scraper (roadmap Phase 2).

    Reads a configurable list of public job feeds and maps each item to a Job,
    handling the common conventions: an explicit ``<company>``/``<dc:creator>``
    tag, a "Company: Role" title (We Work Remotely style), or "Role at Company".
    Only AI/automation-relevant postings are kept. Feeds come from the
    ``RSS_FEEDS`` env var, falling back to a small built-in default set.
    """

    source_name = "rss"
    source_type = "feed"
    # Feeds that add coverage beyond the JSON-API sources already in the project.
    default_feeds = [
        "https://himalayas.app/jobs/rss",
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://jobspresso.co/?feed=job_feed",
    ]

    def __init__(self, limit: int = 50, feeds: list[str] | None = None, **kwargs) -> None:
        super().__init__(limit=limit, **kwargs)
        self.feeds = feeds if feeds is not None else (RSS_FEEDS or self.default_feeds)

    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        jobs: list[Job] = []
        for feed_url in self.feeds:
            jobs.extend(self._fetch_feed(feed_url))
            if len(jobs) >= self.limit:
                return jobs[: self.limit]
        return jobs[: self.limit]

    def _fetch_feed(self, feed_url: str) -> list[Job]:
        try:
            response = self.get(feed_url)
        except Exception as error:
            self.handle_errors(error)
            return []
        soup = BeautifulSoup(response.content, "xml")
        items = soup.find_all("item") or soup.find_all("entry")
        host = urlparse(feed_url).netloc.lower().removeprefix("www.")

        jobs: list[Job] = []
        for item in items:
            job = self._parse_item(item, host)
            if job is None:
                continue
            jobs.append(self.normalize_job(job))
            if len(jobs) >= self.limit:
                break
        return jobs

    def _parse_item(self, item, host: str) -> Job | None:
        title_raw = self._text(item, "title")
        if not title_raw:
            return None
        description_html = (
            self._text(item, "description")
            or self._text(item, "encoded")
            or self._text(item, "content")
            or self._text(item, "summary")
        )
        description = BeautifulSoup(description_html, "lxml").get_text(" ", strip=True) if description_html else ""

        # Match on the TITLE only: full RSS descriptions are noisy company
        # boilerplate that often mentions "AI", which would let unrelated roles
        # (sales, billing, ...) slip through.
        if not is_relevant_text(title_raw):
            return None

        company, title = self._company_and_title(item, title_raw)
        location = (
            self._text(item, "location")
            or self._text(item, "locationRestriction")
            or self._text(item, "region")
            or self._text(item, "country")
            or "Remote"
        )
        return Job(
            job_title=title,
            company_name=company,
            location=location,
            remote_type="remote",
            source_platform=f"rss:{host}",
            source_type=self.source_type,
            job_url=self._link(item),
            date_posted=self._text(item, "pubDate") or self._text(item, "updated") or self._text(item, "published"),
            job_description=description,
            required_skills=self._text(item, "skills"),
        )

    def _company_and_title(self, item, title_raw: str) -> tuple[str, str]:
        explicit = (
            self._text(item, "companyName")
            or self._text(item, "company")
            or self._text(item, "creator")
            or self._author(item)
        )
        if explicit:
            return explicit[:80], title_raw[:120]
        # "Company: Role" -- require ": " (colon + space) so German gender forms
        # like "Finanzbuchhalter:in" are not mistaken for a company.
        separator = title_raw.find(": ")
        if separator != -1:
            company = title_raw[:separator].strip()
            role = title_raw[separator + 2 :].strip()
            return company[:80], (role or title_raw)[:120]
        match = re.search(r"\bat\s+(.+)$", title_raw, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()[:80], title_raw[: match.start()].strip()[:120] or title_raw[:120]
        return "", title_raw[:120]

    def _text(self, item, tag: str) -> str:
        element = item.find(tag)
        return element.get_text(strip=True) if element else ""

    def _author(self, item) -> str:
        author = item.find("author")
        if not author:
            return ""
        name = author.find("name")
        return (name.get_text(strip=True) if name else author.get_text(strip=True))[:80]

    def _link(self, item) -> str:
        element = item.find("link")
        if not element:
            return ""
        return element.get_text(strip=True) or element.get("href", "")
