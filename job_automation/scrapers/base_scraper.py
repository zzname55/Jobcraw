from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

import requests

from config import (
    HTTP_CACHE_PATH,
    HTTP_CIRCUIT_BREAKER_THRESHOLD,
    HTTP_ENABLE_CACHE,
    HTTP_JITTER_SECONDS,
    HTTP_MAX_RETRIES,
    HTTP_RESPECT_ROBOTS,
    SCRAPER_RATE_LIMIT_SECONDS,
)
from database.models import Job
from matching.company_intel import extract_company_size, lookup_company_size
from matching.language_detection import detect_language
from matching.region_detection import detect_location_details
from matching.remote_detection import detect_remote_type
from matching.seniority_detection import detect_seniority
from matching.skills import extract_skills
from scrapers.http_client import HttpClient


# U+FFFD, built via chr() so no literal special character lives in this source.
_REPLACEMENT_CHAR = chr(0xFFFD)


def clean_field(value: str) -> str:
    """Remove source-corrupted characters and collapse whitespace.

    Some feeds (e.g. Arbeitnow) already contain U+FFFD replacement characters
    where a symbol such as the euro sign was mangled upstream, plus the odd stray
    control byte. Strip those so they never reach the exports; tab and newline are
    kept, everything below 0x20 is dropped.
    """
    if not value:
        return value
    cleaned = "".join(
        ch for ch in value if ch in ("\t", "\n") or (ch >= " " and ch != _REPLACEMENT_CHAR)
    )
    return " ".join(cleaned.split())


class BaseScraper(ABC):
    source_name = "base"
    base_url = ""
    source_type = "scraper"

    def __init__(self, limit: int = 50, rate_limit_seconds: float = SCRAPER_RATE_LIMIT_SECONDS) -> None:
        self.limit = limit
        self.rate_limit_seconds = rate_limit_seconds
        self.logger = logging.getLogger(self.source_name)
        self.http = HttpClient(
            rate_limit_seconds=rate_limit_seconds,
            jitter_seconds=HTTP_JITTER_SECONDS,
            max_retries=HTTP_MAX_RETRIES,
            logger=self.logger,
            respect_robots=HTTP_RESPECT_ROBOTS,
            enable_cache=HTTP_ENABLE_CACHE,
            circuit_breaker_threshold=HTTP_CIRCUIT_BREAKER_THRESHOLD,
            cache_path=HTTP_CACHE_PATH or None,
        )
        # Backward-compatible alias; some scrapers/tests reference ``session``.
        self.session = self.http.session

    @abstractmethod
    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        raise NotImplementedError

    def parse_job(self, raw_job: dict[str, Any]) -> Job:
        return Job(**raw_job)

    def normalize_job(self, job: Job) -> Job:
        # Strip source-corrupted characters before detection and export.
        job.job_title = clean_field(job.job_title)
        job.company_name = clean_field(job.company_name)
        job.location = clean_field(job.location)
        job.job_description = clean_field(job.job_description)
        job.salary = clean_field(job.salary)
        text = job.text_blob()
        job.source_platform = job.source_platform or self.source_name
        job.source_type = job.source_type or self.source_type
        job.remote_type = job.remote_type if job.remote_type != "unknown" else detect_remote_type(text)
        job.seniority = job.seniority if job.seniority != "unknown" else detect_seniority(text)
        job.language = job.language if job.language != "unknown" else detect_language(text)
        if not job.region or job.region == "unknown" or not job.country or not job.city:
            location_details = detect_location_details(job.location)
            details = location_details if job.location and location_details["region"] != "unknown" else detect_location_details(text)
            job.region = job.region if job.region and job.region != "unknown" else details["region"]
            job.country = job.country or details["country"]
            job.city = job.city or details["city"]
        if not job.required_skills:
            job.required_skills = extract_skills(text)
        # A curated headcount override (by company name) is authoritative; it makes
        # the <200-employee filter bite for known companies the posting never sizes.
        override = lookup_company_size(job.company_name)
        if override:
            job.company_size, job.company_size_source = override
        elif not job.company_size or job.company_size == "unknown":
            job.company_size, job.company_size_source = extract_company_size(text)
        job.is_startup_likely = job.is_startup_likely or any(term in text.lower() for term in ["startup", "early-stage", "saas", "y combinator"])
        return job

    def respect_rate_limit(self) -> None:
        self.http.respect_rate_limit()

    def handle_errors(self, error: Exception) -> None:
        self.logger.warning("%s skipped after error: %s", self.source_name, error)

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        return self.http.get(url, **kwargs)
