from __future__ import annotations

import random
import re
import time

import config
from database.models import Job
from matching.company_intel import parse_headcount_text
from matching.relevance import is_relevant_text
from scrapers.base_scraper import BaseScraper
from scrapers.jsonld import extract_job_posting, job_posting_fields


class JoinScraper(BaseScraper):
    """Robots-respecting join.com scraper via published JSON-LD JobPosting data.

    join.com has no documented public job API and its search loads over private
    XHR calls, so reverse-engineering that would be fragile and grey-area.
    Instead this scraper uses only what join.com publishes *for* crawlers:

    1. Discover posting URLs with DuckDuckGo ``site:join.com`` queries (a normal
       search engine, no scraping of join.com's own search).
    2. Fetch each public posting page (these live under ``/companies/`` which
       join.com's robots.txt allows; only ``/lp/*`` is disallowed) and read the
       embedded ``application/ld+json`` ``JobPosting`` block -- the
       schema.org structured data sites expose precisely so machines can read
       postings. This yields the real hiring company, full location and
       description, not a guessed company from a search snippet.

    Expired postings return HTTP 410 and pages without a JobPosting block are
    skipped. Requests are paced and capped by ``--limit``.
    """

    source_name = "join"
    source_type = "feed"
    base_url = "https://join.com"
    results_per_query = 12

    # Focused title set; join.com is strong for AI-automation startup roles.
    discovery_titles = [
        "AI Automation Specialist",
        "AI Automation Engineer",
        "Junior AI Automation",
        "Workflow Automation Specialist",
        "AI Workflow Engineer",
        "n8n Automation Specialist",
        "AI Agent Engineer",
        "LLM Automation Engineer",
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._size_cache: dict[str, str] = {}

    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        urls = self._discover_urls(region)
        if not urls:
            return []
        jobs: list[Job] = []
        seen: set[str] = set()
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            job = self._fetch_posting(url)
            if job is not None:
                jobs.append(self.normalize_job(job))
            self._pace()
            if len(jobs) >= self.limit:
                break
        return jobs

    def _discover_urls(self, region: str = "worldwide") -> list[str]:
        try:
            from ddgs import DDGS
        except ImportError:
            self.logger.info("ddgs not installed (pip install ddgs); skipping join.com discovery.")
            return []
        region_term = {"germany": "Germany", "dach": "DACH", "europe": "Europe"}.get(region.lower(), "Remote")
        urls: list[str] = []
        with DDGS() as ddgs:
            for title in self.discovery_titles:
                query = f'site:join.com "{title}" {region_term}'
                try:
                    results = list(ddgs.text(query, max_results=self.results_per_query))
                except Exception as error:
                    self.handle_errors(error)
                    self._pace()
                    continue
                for item in results:
                    href = str(item.get("href") or "")
                    if self._is_posting_url(href):
                        urls.append(href.split("?")[0])
                self._pace()
        return list(dict.fromkeys(urls))

    @staticmethod
    def _is_posting_url(href: str) -> bool:
        # A real posting looks like /companies/<slug>/<id>-<role-slug>; the bare
        # company page (/companies/<slug>) and landing pages are not postings.
        return bool(re.search(r"join\.com/companies/[^/]+/\d+", href))

    def _fetch_posting(self, url: str) -> Job | None:
        try:
            response = self.get(url)
        except Exception as error:
            self.handle_errors(error)
            return None
        if response.status_code == 410 or response.status_code >= 400:
            return None  # expired or unavailable posting
        posting = extract_job_posting(response.text)
        if not posting:
            return None
        fields = job_posting_fields(posting)
        title = fields["title"]
        if not title or not is_relevant_text(title):
            return None
        organization = posting.get("hiringOrganization")
        company_url = organization.get("url", "") if isinstance(organization, dict) else ""
        company_size = self._company_headcount(company_url)
        return Job(
            job_title=title[:160],
            company_name=fields["company"][:80] or "Unknown",
            location=fields["location"] or "Unknown",
            remote_type="remote" if fields["remote_type"] else "unknown",
            source_platform="join.com",
            source_type=self.source_type,
            job_url=url,
            date_posted=fields["date_posted"],
            job_description=fields["description"],
            salary=fields["salary"],
            company_size=company_size or "unknown",
            company_size_source="join.com company page" if company_size else "",
        )

    def _company_headcount(self, company_url: str) -> str:
        """Fetch the join.com company page for its headcount (opt-in, memoized)."""
        if not config.JOIN_FETCH_COMPANY_SIZE or not company_url:
            return ""
        if company_url in self._size_cache:
            return self._size_cache[company_url]
        size = ""
        try:
            response = self.get(company_url)
            if response.status_code < 400:
                size = parse_headcount_text(response.text)
        except Exception as error:
            self.handle_errors(error)
        self._size_cache[company_url] = size
        self._pace()
        return size

    def _pace(self) -> None:
        if self.rate_limit_seconds > 0:
            time.sleep(self.rate_limit_seconds + random.uniform(0, 0.5))
