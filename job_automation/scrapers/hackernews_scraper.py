from __future__ import annotations

import re

from bs4 import BeautifulSoup

from database.models import Job
from matching.keywords import TARGET_TITLES
from matching.relevance import is_relevant_text
from scrapers.base_scraper import BaseScraper


# Role words used to pull a job title out of a free-form HN header line.
ROLE_WORDS = (
    "engineer",
    "developer",
    "scientist",
    "specialist",
    "manager",
    "designer",
    "analyst",
    "architect",
    "consultant",
    "programmer",
    "researcher",
    "lead",
    "ops",
    "sre",
)


class HackerNewsHiringScraper(BaseScraper):
    """Hacker News monthly "Ask HN: Who is hiring?" thread via the Algolia API.

    The thread is posted by the ``whoishiring`` account each month; every top-level
    comment is one company's posting, loosely formatted as
    ``Company | location | REMOTE | role | url``. This is a key-free, AI-startup-rich
    source. Only AI/automation-relevant postings are kept (roadmap Phase 2).
    """

    source_name = "hackernews"
    source_type = "feed"
    search_url = "https://hn.algolia.com/api/v1/search_by_date"
    item_url = "https://hn.algolia.com/api/v1/items/{story_id}"

    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        story_id = self._latest_thread_id()
        if not story_id:
            self.logger.info("No 'Who is hiring' thread found on Hacker News.")
            return []
        try:
            item = self.get(self.item_url.format(story_id=story_id)).json()
        except Exception as error:
            self.handle_errors(error)
            return []

        jobs: list[Job] = []
        for comment in item.get("children", []) or []:
            job = self._parse_comment(comment)
            if job is None:
                continue
            jobs.append(self.normalize_job(job))
            if len(jobs) >= self.limit:
                break
        return jobs

    def _latest_thread_id(self) -> str | None:
        try:
            data = self.get(self.search_url, params={"tags": "story,author_whoishiring", "hitsPerPage": 12}).json()
        except Exception as error:
            self.handle_errors(error)
            return None
        for hit in data.get("hits", []) or []:
            # Pick "Who is hiring?", not the sibling "Who wants to be hired?".
            if "who is hiring" in str(hit.get("title") or "").lower():
                return str(hit.get("objectID") or "")
        return None

    def _parse_comment(self, comment: dict) -> Job | None:
        raw = str(comment.get("text") or "")
        header_html = raw.split("<p>")[0]
        if "|" not in header_html:  # standard postings are pipe-delimited
            return None
        full_text = BeautifulSoup(raw, "lxml").get_text(" ", strip=True)
        if not is_relevant_text(full_text):
            return None

        link = BeautifulSoup(raw, "lxml").find("a", href=True)
        job_url = link["href"] if link else ""
        header = BeautifulSoup(header_html, "lxml").get_text(" ", strip=True)
        pieces = [piece.strip() for piece in header.split("|") if piece.strip()]
        company = self._clean_company(pieces[0]) if pieces else ""
        if not company:
            return None

        return Job(
            job_title=self._role(pieces[1:], full_text),
            company_name=company,
            location=self._location(pieces[1:]),
            remote_type=self._remote_type(full_text),
            source_platform=self.source_name,
            source_type=self.source_type,
            job_url=job_url,
            job_description=full_text[:4000],
        )

    def _clean_company(self, value: str) -> str:
        value = re.sub(r"\(.*?\)", "", value)  # drop "(url)" / "(Backed by ...)" first
        value = re.sub(r"https?://\S+", "", value)
        # Drop investor / funding annotations that sometimes lead the header.
        value = re.sub(r"\b(backed|back)\s+by\b.*$", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s+", " ", value).strip(" *-|–—•·")
        return value[:80]

    def _looks_like_location_or_salary(self, piece: str) -> bool:
        lowered = piece.lower()
        if "$" in piece or "€" in piece or "£" in piece:
            return True
        if re.search(r"\d{2,}\s*[k,]", lowered):  # salary figures like 175,000 or 120k
            return True
        return any(word in lowered for word in ROLE_WORDS)

    def _remote_type(self, text: str) -> str:
        lowered = text.lower()
        if re.search(r"\bhybrid\b", lowered):
            return "hybrid"
        if re.search(r"\bremote\b", lowered):
            return "remote"
        if re.search(r"\b(onsite|on-site|in office|in-office)\b", lowered):
            return "onsite"
        return "unknown"

    def _role(self, pieces: list[str], text: str) -> str:
        lowered = text.lower()
        for target in TARGET_TITLES:
            if target in lowered:
                return target.title()
        # A common role phrase anywhere in the posting, e.g. "Senior AI Engineer",
        # "Founding Full-stack Developer", "Applied ML Scientist".
        match = re.search(
            r"\b(?:senior|junior|lead|staff|principal|founding|applied|forward[- ]deployed)?\s*"
            r"(?:ai|ml|machine learning|software|full[- ]?stack|back[- ]?end|front[- ]?end|platform|data|automation|infrastructure)?\s*"
            r"(?:engineer|developer|scientist|specialist)s?\b",
            text,
            flags=re.IGNORECASE,
        )
        if match and match.group(0).strip():
            return re.sub(r"\s+", " ", match.group(0)).strip()[:80]
        for piece in pieces:
            piece_lower = piece.lower()
            if "http" in piece_lower or "www." in piece_lower:
                continue
            if self._looks_like_location_or_salary(piece):
                continue
            if any(word in piece_lower for word in ROLE_WORDS):
                return piece[:80]
        return "AI / Automation role"

    def _location(self, pieces: list[str]) -> str:
        for piece in pieces:
            piece_lower = piece.lower()
            if "http" in piece_lower or "www." in piece_lower or len(piece) > 40:
                continue
            if re.search(r"\b(remote|onsite|on-site|hybrid|full[- ]time|part[- ]time|contract|intern)\b", piece_lower):
                continue
            if self._looks_like_location_or_salary(piece):
                continue
            if "," in piece or re.search(
                r"\b(usa|uk|eu|europe|germany|berlin|munich|london|nyc|new york|san francisco|sf|amsterdam|paris|canada|austin|boston)\b",
                piece_lower,
            ):
                return piece[:60]
        return ""
