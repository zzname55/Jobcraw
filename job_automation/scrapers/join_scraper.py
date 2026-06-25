from __future__ import annotations

import html
import json
import random
import re
import time
from typing import Any

from bs4 import BeautifulSoup

from database.models import Job
from matching.relevance import is_relevant_text
from scrapers.base_scraper import BaseScraper


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
        posting = self._extract_job_posting(response.text)
        if not posting:
            return None
        title = self._clean_text(html.unescape(str(posting.get("title") or "")))
        if not title or not is_relevant_text(title):
            return None
        return Job(
            job_title=title[:160],
            company_name=self._org_name(posting)[:80] or "Unknown",
            location=self._location(posting),
            remote_type="remote" if "remote" in (posting.get("jobLocationType") or "").lower() else "unknown",
            source_platform="join.com",
            source_type=self.source_type,
            job_url=url,
            date_posted=str(posting.get("datePosted") or ""),
            job_description=self._description(posting),
        )

    def _extract_job_posting(self, page_html: str) -> dict[str, Any] | None:
        soup = BeautifulSoup(page_html, "lxml")
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = script.string or script.get_text() or ""
            if "JobPosting" not in raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            for candidate in self._iter_objects(data):
                if isinstance(candidate, dict) and candidate.get("@type") == "JobPosting":
                    return candidate
        return None

    @staticmethod
    def _iter_objects(data: Any):
        if isinstance(data, list):
            for item in data:
                yield from JoinScraper._iter_objects(item)
        elif isinstance(data, dict):
            yield data
            if "@graph" in data:
                yield from JoinScraper._iter_objects(data["@graph"])

    def _org_name(self, posting: dict[str, Any]) -> str:
        org = posting.get("hiringOrganization")
        if isinstance(org, dict):
            return self._clean_text(html.unescape(str(org.get("name") or "")))
        return self._clean_text(html.unescape(str(org or "")))

    def _location(self, posting: dict[str, Any]) -> str:
        location = posting.get("jobLocation")
        if isinstance(location, list):
            location = location[0] if location else None
        if isinstance(location, dict):
            address = location.get("address", {})
            if isinstance(address, dict):
                city = address.get("addressLocality") or ""
                country = address.get("addressRegion") or address.get("addressCountry") or ""
                joined = ", ".join(part for part in (city, country) if part)
                if joined:
                    return self._clean_text(joined)
        if (posting.get("jobLocationType") or "").upper() == "TELECOMMUTE":
            return "Remote"
        return "Unknown"

    def _description(self, posting: dict[str, Any]) -> str:
        raw = html.unescape(str(posting.get("description") or ""))
        text = BeautifulSoup(raw, "lxml").get_text(" ", strip=True)
        return self._clean_text(text)[:7000]

    @staticmethod
    def _clean_text(value: str) -> str:
        return " ".join((value or "").split())

    def _pace(self) -> None:
        if self.rate_limit_seconds > 0:
            time.sleep(self.rate_limit_seconds + random.uniform(0, 0.5))
