from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import requests

from config import SCRAPER_RATE_LIMIT_SECONDS
from database.models import Job
from matching.company_intel import extract_company_size
from matching.language_detection import detect_language
from matching.region_detection import detect_location_details
from matching.remote_detection import detect_remote_type
from matching.seniority_detection import detect_seniority
from matching.skills import extract_skills


class BaseScraper(ABC):
    source_name = "base"
    base_url = ""
    source_type = "scraper"

    def __init__(self, limit: int = 50, rate_limit_seconds: float = SCRAPER_RATE_LIMIT_SECONDS) -> None:
        self.limit = limit
        self.rate_limit_seconds = rate_limit_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "job-automation-mvp/1.0 (+respectful public job discovery)",
                "Accept": "text/html,application/json,application/rss+xml",
            }
        )
        self.logger = logging.getLogger(self.source_name)

    @abstractmethod
    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        raise NotImplementedError

    def parse_job(self, raw_job: dict[str, Any]) -> Job:
        return Job(**raw_job)

    def normalize_job(self, job: Job) -> Job:
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
        if not job.company_size or job.company_size == "unknown":
            job.company_size, job.company_size_source = extract_company_size(text)
        job.is_startup_likely = job.is_startup_likely or any(term in text.lower() for term in ["startup", "early-stage", "saas", "y combinator"])
        return job

    def respect_rate_limit(self) -> None:
        if self.rate_limit_seconds > 0:
            time.sleep(self.rate_limit_seconds)

    def handle_errors(self, error: Exception) -> None:
        self.logger.warning("%s skipped after error: %s", self.source_name, error)

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        self.respect_rate_limit()
        response = self.session.get(url, timeout=20, **kwargs)
        response.raise_for_status()
        return response
