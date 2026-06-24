from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from bs4 import BeautifulSoup

from config import COMPANIES_FILE
from database.models import Job
from matching.skills import term_in_text
from scrapers.base_scraper import BaseScraper


# Title terms that mark a posting as relevant to this project. ATS boards return
# *every* open role at a company, so we keep only AI/automation-flavoured ones
# instead of flooding the pipeline with unrelated jobs. Scoring still has the
# final say; this is just a cheap pre-filter.
RELEVANT_TITLE_TERMS = [
    "ai",
    "ml",
    "machine learning",
    "applied ai",
    "llm",
    "gpt",
    "agent",
    "agents",
    "agentic",
    "automation",
    "automatisierung",
    "workflow",
    "n8n",
    "zapier",
    "make.com",
    "no-code",
    "low-code",
    "rpa",
    "mcp",
    "integration",
    "solutions engineer",
    "forward deployed",
]


def load_companies(path: Path | str) -> dict[str, list[str]]:
    """Read the ATS slug list from a YAML file.

    Expected shape::

        greenhouse:
          - some-company
        lever:
          - another-company

    Missing file or empty sections are tolerated and return empty lists.
    """
    file_path = Path(path)
    if not file_path.exists():
        return {}
    data = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    companies: dict[str, list[str]] = {}
    for provider in ("greenhouse", "lever"):
        raw = data.get(provider) or []
        companies[provider] = [str(slug).strip() for slug in raw if str(slug).strip()]
    return companies


class AtsScraper(BaseScraper):
    """Key-free scraper for public Applicant Tracking System (ATS) job boards.

    Hits the documented public JSON endpoints of Greenhouse and Lever, which are
    meant to be consumed and are not anti-bot protected. Company slugs come from
    ``companies.yaml`` (see SCRAPER_ROADMAP.md, section 2).
    """

    source_name = "ats"
    source_type = "ats_api"

    def __init__(self, limit: int = 50, companies_file: Path | str = COMPANIES_FILE, **kwargs: Any) -> None:
        super().__init__(limit=limit, **kwargs)
        self.companies_file = Path(companies_file)

    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        companies = load_companies(self.companies_file)
        if not companies.get("greenhouse") and not companies.get("lever"):
            self.logger.info("No ATS company slugs configured in %s. Skipping ATS scraper.", self.companies_file)
            return []

        jobs: list[Job] = []
        for slug in companies.get("greenhouse", []):
            jobs.extend(self._fetch_greenhouse(slug))
            if len(jobs) >= self.limit:
                return jobs[: self.limit]
        for slug in companies.get("lever", []):
            jobs.extend(self._fetch_lever(slug))
            if len(jobs) >= self.limit:
                return jobs[: self.limit]
        return jobs[: self.limit]

    def _fetch_greenhouse(self, slug: str) -> list[Job]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
        try:
            payload = self.get(url).json()
        except Exception as error:
            self.handle_errors(error)
            return []

        jobs: list[Job] = []
        for item in payload.get("jobs", []):
            title = str(item.get("title") or "")
            if not self._is_relevant_title(title):
                continue
            location = ""
            if isinstance(item.get("location"), dict):
                location = str(item["location"].get("name") or "")
            job = Job(
                job_title=title,
                company_name=self._prettify_slug(slug),
                location=location,
                source_platform=f"greenhouse:{slug}",
                source_type=self.source_type,
                job_url=str(item.get("absolute_url") or ""),
                date_posted=str(item.get("updated_at") or ""),
                job_description=self._html_to_text(str(item.get("content") or "")),
            )
            jobs.append(self.normalize_job(job))
            if len(jobs) >= self.limit:
                break
        return jobs

    def _fetch_lever(self, slug: str) -> list[Job]:
        url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
        try:
            payload = self.get(url).json()
        except Exception as error:
            self.handle_errors(error)
            return []

        jobs: list[Job] = []
        for item in payload if isinstance(payload, list) else []:
            title = str(item.get("text") or "")
            if not self._is_relevant_title(title):
                continue
            categories = item.get("categories") or {}
            location = str(categories.get("location") or "")
            description = self._html_to_text(str(item.get("description") or ""))
            commitment = str(categories.get("commitment") or "")
            team = str(categories.get("team") or "")
            job = Job(
                job_title=title,
                company_name=self._prettify_slug(slug),
                location=location,
                source_platform=f"lever:{slug}",
                source_type=self.source_type,
                job_url=str(item.get("hostedUrl") or item.get("applyUrl") or ""),
                date_posted=str(item.get("createdAt") or ""),
                job_description=" ".join(part for part in [commitment, team, description] if part),
            )
            jobs.append(self.normalize_job(job))
            if len(jobs) >= self.limit:
                break
        return jobs

    def _is_relevant_title(self, title: str) -> bool:
        return any(term_in_text(title, term) for term in RELEVANT_TITLE_TERMS)

    def _prettify_slug(self, slug: str) -> str:
        return slug.replace("-", " ").replace("_", " ").strip().title() or "Unknown"

    def _html_to_text(self, content: str) -> str:
        if not content:
            return ""
        text = BeautifulSoup(content, "lxml").get_text(" ", strip=True)
        return " ".join(text.split())[:7000]
