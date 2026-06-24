from __future__ import annotations

import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from database.models import Job


TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "ref", "source"}
COMPANY_SUFFIXES = (" gmbh", " ltd", " inc", " llc", " ag", " se")


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower()).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for suffix in COMPANY_SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
    return normalized


def normalize_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url)
    query = urlencode([(key, value) for key, value in parse_qsl(parts.query) if key.lower() not in TRACKING_PARAMS])
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), query, ""))


def prepare_deduplication(job: Job) -> Job:
    normalized_title = normalize_text(job.job_title)
    normalized_company = normalize_text(job.company_name)
    location = normalize_text(job.location)
    url = normalize_url(job.job_url)
    job.job_url = url
    job.normalized_title = normalized_title
    job.normalized_company = normalized_company
    job.deduplication_key = url or build_job_signature(normalized_title, normalized_company, location)
    return job


def build_job_signature(normalized_title: str, normalized_company: str, location: str) -> str:
    title = re.sub(r"\b(junior|senior|lead|remote|hybrid|m f d|f m d|w m d|all genders)\b", " ", normalized_title)
    title = re.sub(r"\s+", " ", title).strip()
    location_key = "remote" if "remote" in location else location[:30]
    return "|".join(part for part in [title, normalized_company, location_key] if part)


def deduplicate_jobs(jobs: list[Job]) -> list[Job]:
    seen_urls: set[str] = set()
    seen_keys: set[str] = set()
    seen_signatures: set[str] = set()
    unique_jobs: list[Job] = []
    for job in jobs:
        prepared = prepare_deduplication(job)
        signature = build_job_signature(prepared.normalized_title, prepared.normalized_company, normalize_text(prepared.location))
        if prepared.job_url and prepared.job_url in seen_urls:
            continue
        if prepared.deduplication_key in seen_keys:
            continue
        if signature in seen_signatures:
            continue
        if prepared.job_url:
            seen_urls.add(prepared.job_url)
        seen_keys.add(prepared.deduplication_key)
        seen_signatures.add(signature)
        unique_jobs.append(prepared)
    return unique_jobs
