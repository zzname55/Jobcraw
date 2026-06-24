from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from config import BING_SEARCH_API_KEY, GOOGLE_SEARCH_API_KEY, SERPAPI_API_KEY, SERPAPI_CAPTURE_DIR, SERPAPI_FETCH_DETAILS
from database.models import Job
from matching.keywords import TARGET_TITLES
from matching.region_detection import GEOGRAPHIC_NAMES, is_location_name
from scrapers.base_scraper import BaseScraper


class GenericSearchScraper(BaseScraper):
    source_name = "generic_search"
    source_type = "search_api"
    fetch_details = SERPAPI_FETCH_DETAILS
    blocked_domains = {
        "linkedin.com",
        "x.com",
        "twitter.com",
        "facebook.com",
        "instagram.com",
        "careerexplorer.com",
        "talentsurge.io",
        "community.n8n.io",
        "jobicy.com",
        "reval.site",
        "glassdoor.com",
        "glassdoor.de",
        "glassdoor.co.in",
        "jobleads.com",
        # Reference / dictionary / encyclopedia / movie / streaming / video.
        # These match single dictionary words like "junior" and are never jobs.
        "merriam-webster.com",
        "wiktionary.org",
        "wikipedia.org",
        "dictionary.com",
        "imdb.com",
        "rottentomatoes.com",
        "youtube.com",
        "netflix.com",
        "themoviedb.org",
        "genaisummit.eu",
    }
    weak_aggregator_domains = {
        "indeed.com",
        "ziprecruiter.com",
        "careerjet.com",
        "careerjet.ua",
        "bebee.com",
        "jooble.org",
    }
    job_board_domains = {
        "tanqeeb.com",
        "trabajo.org",
        "expertini.com",
        "onlinejobs.ph",
        "djinni.co",
        "jaabz.com",
        "remotefront.com",
        "builtinsf.com",
        "builtin.com",
        "builtinboston.com",
        # Aggregators / job boards: the real employer is rarely the domain name,
        # so fall back to "Unknown" instead of using the board name as company.
        "himalayas.app",
        "aidoos.com",
        "lensa.com",
        "jobgether.com",
        "recruit.net",
        "dailyremote.com",
        "talent.outsized.com",
        "startup.jobs",
        "meetfrank.com",
        "remoterocketship.com",
        "africashore.com",
        "jobtensor.com",
        "vaia.com",
        "studysmarter.de",
        "social-networking.me",
        "railway.app",
        "page.gd",
    }
    geographic_domain_tokens = {
        "egypt",
        "de",
        "br",
        "cabedelo",
        "pt",
        "es",
        "uk",
        "gb",
        "us",
        "ph",
    }
    noisy_title_patterns = [
        "jobs, employment",
        "hiring now",
        "what does",
        "hire an",
        "hire a",
        "freelance gigs",
        "remote jobs matching",
        "job search",
        "jobs with salaries",
        "jobs in ",
        "open jobs",
        "latest jobs",
        "salary guide",
        "salary benchmark",
        "salary report",
        "career path",
        "skills & advice",
        "specializing in",
        "community",
        "definition & meaning",
        "official trailer",
        "testimonials",
        "jobs - work from home",
        "best remote",
    ]
    noisy_path_patterns = [
        "/jobs?",
        "/jobs/",
        "/job-search",
        "/search",
        "/salaries",
        "/career-advice",
    ]
    hard_noisy_path_patterns = [
        "/services/",
        "/top",
        "/u/",
    ]

    def build_queries(self, region: str = "worldwide", remote: bool = True) -> list[str]:
        region_terms = self._region_terms(region, remote)
        priority_titles = [
            "Junior AI Automation Specialist",
            "AI Automation Specialist",
            "Junior Workflow Automation Specialist",
            "AI Workflow Specialist",
            "Junior AI Solutions Specialist",
            "AI Implementation Specialist",
            "AI Enablement Specialist",
            "AI Process Automation Specialist",
            "Business Process Automation Specialist AI",
            "No-Code AI Automation Specialist",
            "Low-Code AI Automation Specialist",
            "n8n Automation Specialist",
            "Junior n8n Specialist",
            "AI Agents Specialist",
            "Junior AI Agent Engineer",
            "Agentic Systems Engineer",
            "LLM Automation Specialist",
            "MCP Server Developer",
            "MCP Integration Engineer",
            "AI Tooling Engineer",
            "RevOps Automation Specialist",
            "GTM Automation Engineer AI",
            "Sales Automation Specialist AI",
            "Operations Automation Specialist",
        ]
        concept_queries = [
            '"workflow automation" "AI agents"',
            '"MCP server" "AI agents"',
            '"agentic systems" engineer',
            '"Model Context Protocol" engineer',
            '"LLM automation" workflow',
        ]
        sites = ["site:join.com", "site:wellfound.com", "site:ycombinator.com/jobs", "site:berlinstartupjobs.com", "site:germantechjobs.de"]
        queries: list[str] = []
        for index, title in enumerate(priority_titles):
            region_term = region_terms[index % len(region_terms)]
            queries.append(f'"{title}" "{region_term}"')
            if len(queries) >= self.limit:
                return queries
        for index, query in enumerate(concept_queries):
            region_term = region_terms[index % len(region_terms)]
            queries.append(f'{query} "{region_term}" job')
            if len(queries) >= self.limit:
                return queries
        for site in sites:
            for region_term in region_terms:
                for title in TARGET_TITLES[:24]:
                    queries.append(f'{site} "{title}" "{region_term}"')
                    if len(queries) >= self.limit:
                        return queries
        return queries

    def _region_terms(self, region: str, remote: bool) -> list[str]:
        base_terms = {
            "germany": ["Germany", "Remote Germany", "Hybrid Germany"],
            "dach": ["Germany", "DACH", "Remote DACH", "Austria", "Switzerland"],
            "europe": ["Germany", "DACH", "Europe", "Remote Europe", "Hybrid Europe"],
            "worldwide": ["Remote", "Worldwide Remote", "Remote Europe", "Germany", "DACH"],
        }
        terms = base_terms.get(region.lower(), [region])
        if remote and region.lower() == "worldwide":
            terms = ["Remote", "Hybrid", *terms]
        return list(dict.fromkeys(terms))

    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        if SERPAPI_API_KEY:
            return self._search_serpapi(region, remote)
        if BING_SEARCH_API_KEY or GOOGLE_SEARCH_API_KEY:
            self.logger.info("Bing/Google API keys detected, but this MVP only implements SerpAPI result parsing.")
            return []
        self.logger.info("No search API key configured. Skipping Generic Search Scraper.")
        return []

    def _search_serpapi(self, region: str, remote: bool) -> list[Job]:
        jobs: list[Job] = []
        # For Generic Search, ``limit`` intentionally controls the number of
        # SerpAPI queries so test runs can cap API-credit usage predictably.
        for index, query in enumerate(self.build_queries(region, remote)):
            try:
                response = self.get(
                    "https://serpapi.com/search.json",
                    params={"engine": "google", "q": query, "api_key": SERPAPI_API_KEY},
                    bypass_robots=True,
                )
                data = response.json()
            except Exception as error:
                self.handle_errors(error)
                continue
            self._capture_response(index, query, data)
            jobs.extend(self._parse_serpapi_results(data, query))
        return jobs

    def _capture_response(self, index: int, query: str, data: dict[str, Any]) -> None:
        if not SERPAPI_CAPTURE_DIR:
            return
        capture_dir = Path(SERPAPI_CAPTURE_DIR)
        capture_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")[:60]
        path = capture_dir / f"{index:02d}_{safe}.json"
        try:
            path.write_text(json.dumps({"query": query, "data": data}, ensure_ascii=False, indent=2), encoding="utf-8")
            self.logger.info("captured SerpAPI response: %s", path)
        except Exception as error:
            self.handle_errors(error)

    def _parse_serpapi_results(self, data: dict[str, Any], query: str) -> list[Job]:
        jobs: list[Job] = []
        detail_fetches = 0
        max_detail_fetches = max(10, self.limit * 5)
        for result in data.get("organic_results", []):
            title = str(result.get("title") or "")
            link = str(result.get("link") or "")
            snippet = str(result.get("snippet") or "")
            if not title or not link or self._is_noisy_result(title, link):
                continue
            domain = self._domain(link)
            company_name = self._guess_company(title, domain)
            title = self._clean_title(title)
            description = snippet
            page_title = ""
            if self.fetch_details and detail_fetches < max_detail_fetches:
                page_title, page_text = self._fetch_job_detail_text(link)
                detail_fetches += 1
                if page_title and not self._is_noisy_result(page_title, link):
                    company_name = self._guess_company(page_title, domain)
                    title = self._clean_title(page_title)
                if page_text:
                    description = self._merge_description(snippet, page_text)
            location = self._guess_location(query, description)
            job = Job(
                job_title=title,
                company_name=company_name,
                location=location,
                source_platform=f"serpapi:{domain}",
                source_type=self.source_type,
                job_url=link,
                job_description=description,
            )
            jobs.append(self.normalize_job(job))
        return jobs

    def _is_noisy_result(self, title: str, link: str) -> bool:
        title_lower = title.lower()
        domain = self._domain(link)
        root_domain = ".".join(domain.split(".")[-2:])
        path = urlparse(link).path.lower()
        if domain in self.blocked_domains or root_domain in self.blocked_domains:
            return True
        if any(pattern in path for pattern in self.hard_noisy_path_patterns):
            return True
        if root_domain in self.weak_aggregator_domains and any(pattern in path for pattern in self.noisy_path_patterns):
            return True
        if any(pattern in title_lower for pattern in self.noisy_title_patterns):
            return True
        if re.search(r"\b\d{3,}[,\d]*\+?\s+", title_lower):
            return True
        if len(path.strip("/")) <= 2 and root_domain in self.weak_aggregator_domains:
            return True
        return False

    def _domain(self, link: str) -> str:
        return urlparse(link).netloc.lower().removeprefix("www.")

    def _guess_company(self, title: str, domain: str) -> str:
        # Handle English "at X", German "bei X" and "@ X"; stop at separators so a
        # trailing location or call-to-action is not captured as the company.
        match = re.search(r"(?:\bat\s+|\bbei\s+|@\s*)([^|,–—-]+)", title, flags=re.IGNORECASE)
        if match:
            candidate = self._clean_company(match.group(1))
            if not self._is_bad_company(candidate):
                return candidate
        ignored_suffixes = {"jazzhr", "greenhouse", "lever", "workable", "ashby", "apply", "careers", "jobs"}
        pieces = [piece.strip() for piece in re.split(r"\s[-|–—]\s", title) if piece.strip()]
        if len(pieces) >= 2 and "built in" in pieces[-1].lower():
            candidate = self._clean_company(pieces[-2])
            if not self._is_bad_company(candidate):
                return candidate
        for candidate in reversed(pieces[1:]):
            candidate_key = candidate.lower()
            if candidate_key in ignored_suffixes or re.search(r"\b(remote|hybrid|job|jobs|career|careers)\b", candidate_key):
                continue
            cleaned = self._clean_company(candidate)
            if self._is_bad_company(cleaned):
                continue
            return cleaned
        root_domain = ".".join(domain.split(".")[-2:])
        if domain in self.job_board_domains or root_domain in self.job_board_domains:
            return "Unknown"
        parts = [
            part
            for part in domain.split(".")
            if part not in {"com", "co", "io", "jobs", "careers"} and part not in self.geographic_domain_tokens
        ]
        guess = parts[0].replace("-", " ").title() if parts else "Unknown"
        return "Unknown" if self._is_bad_company(guess) else guess

    def _clean_company(self, value: str) -> str:
        cleaned = re.sub(r"\s+", " ", value or "").strip(" -–—|")
        cleaned = re.sub(
            r"\s+(Djinni|JazzHR|Greenhouse|Lever|Ashby|Workable|Built In.*|Jetzt bewerben.*|Apply Now.*)$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        return cleaned.strip(" -–—|") or "Unknown"

    def _is_bad_company(self, candidate: str) -> bool:
        """Reject obviously-wrong company guesses (CTAs, job ids, places, noise)."""
        key = " ".join((candidate or "").split()).strip(" ()[].,").lower()
        if not key or key == "unknown":
            return True
        if is_location_name(candidate):
            return True
        letters = sum(character.isalpha() for character in candidate)
        if letters < 2:  # pure job ids / numbers / punctuation
            return True
        tokens = re.findall(r"[a-zäöüß0-9&.+-]+", key)
        if tokens and tokens[0] in GEOGRAPHIC_NAMES:  # leading place, e.g. "DACH in Hamburg"
            return True
        if re.search(r"\b(department|abteilung|team|jetzt bewerben|bewerben|apply now|work from home|home office|remote jobs|freelancers?)\b", key):
            return True
        return key in {"apply", "careers", "jobs", "remote", "hybrid", "new", "work from home", "freelance"}

    def _fetch_job_detail_text(self, link: str) -> tuple[str, str]:
        if not link.startswith(("http://", "https://")):
            return "", ""
        if link.lower().endswith((".pdf", ".png", ".jpg", ".jpeg", ".zip")):
            return "", ""
        try:
            response = self.get(link)
        except Exception as error:
            self.handle_errors(error)
            return "", ""
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type.lower():
            return "", ""
        soup = BeautifulSoup(response.text, "lxml")
        for element in soup(["script", "style", "noscript", "svg"]):
            element.decompose()
        page_title = self._clean_title(soup.title.get_text(" ", strip=True) if soup.title else "")
        text = " ".join(soup.get_text(" ", strip=True).split())
        return page_title, text[:6000]

    def _clean_title(self, title: str) -> str:
        cleaned = re.sub(r"\s+", " ", title or "").strip()
        cleaned = re.sub(
            r"\s*\|\s*(Jobs?|Careers?|Apply|LinkedIn|Built In.*|Strider Jobs|Visa Sponsorship Jobs|Jetzt bewerben.*|Remote Jobs on.*).*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        # Trailing call-to-action after a dash, e.g. "... - Jetzt bewerben!".
        cleaned = re.sub(r"\s*[-–—]\s*(Jetzt bewerben|Apply Now|Work From Home)\!?.*$", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip(" -–—|")[:160]

    def _merge_description(self, snippet: str, page_text: str) -> str:
        values = [value.strip() for value in [snippet, page_text] if value and value.strip()]
        return "\n\n".join(dict.fromkeys(values))[:7000]

    def _guess_location(self, query: str, description: str) -> str:
        text = f"{description} {query}"
        patterns = [
            r"\b(remote\s+(germany|europe|dach|worldwide))\b",
            r"\b(hybrid\s+(berlin|germany|europe|dach))\b",
            r"\b(onsite\s+[^.,;|]{2,40})\b",
            r"\b(berlin|munich|münchen|hamburg|frankfurt|germering|vienna|wien|zurich|zürich|london|amsterdam|paris)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip().title()
        quoted_terms = re.findall(r'"([^"]+)"', query)
        return quoted_terms[-1] if quoted_terms else "Unknown"


class CachedSearchScraper(GenericSearchScraper):
    """Re-parse previously captured SerpAPI responses -- no API call, no credits.

    When SerpAPI runs are captured (``SERPAPI_CAPTURE_DIR``), this source turns
    that already-paid-for data into Jobs offline, so the free pipeline keeps the
    value of past searches without spending more credits. Detail-page fetching is
    off by design (fully offline).
    """

    source_name = "cached_search"
    source_type = "cached"
    fetch_details = False

    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        if not SERPAPI_CAPTURE_DIR:
            self.logger.info("No SERPAPI_CAPTURE_DIR set; nothing to replay.")
            return []
        capture_dir = Path(SERPAPI_CAPTURE_DIR)
        if not capture_dir.exists():
            return []
        jobs: list[Job] = []
        for path in sorted(capture_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception as error:
                self.handle_errors(error)
                continue
            data = payload.get("data", payload)
            query = payload.get("query", "")
            jobs.extend(self._parse_serpapi_results(data, query))
            if len(jobs) >= self.limit:
                break
        return jobs[: self.limit]
