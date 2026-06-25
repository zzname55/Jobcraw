from __future__ import annotations

import re
from datetime import datetime

from database.models import Job
from matching.compensation import analyze_compensation_and_hours


# Work-mode and "anywhere" words that are NOT a real geographic location. They
# belong in the Remote column, never in Location.
_WORK_MODE_RE = re.compile(
    r"\b(remote|hybrid|on-?site|online|work\s*from\s*home|wfh|home\s*office|"
    r"anywhere|worldwide|distributed|global)\b",
    flags=re.IGNORECASE,
)


def _strip_work_mode(text: str) -> str:
    """Drop remote/hybrid/worldwide words and leftover separators from free text."""
    cleaned = _WORK_MODE_RE.sub(" ", text or "")
    cleaned = re.sub(r"[\s,;/|()\-–—]+", " ", cleaned).strip()
    return cleaned if any(character.isalpha() for character in cleaned) else ""


def display_location(job: Job) -> str:
    """Real geographic location for the Location column.

    Never returns "Remote"/"Hybrid" (that lives in the Remote column). Prefers the
    detected city/country, falls back to the free-text location with work-mode
    words stripped, and uses "Unknown" when no real place is known.
    """
    city = (job.city or "").strip()
    if city.lower() in {"", "unknown"}:
        city = ""
    country = (job.country or "").strip()
    if country.lower() in {"", "unknown"}:
        country = ""
    if city and country:
        return f"{city}, {country.title()}"
    if city:
        return city
    if country:
        return country.title()
    geographic = _strip_work_mode(job.location or "")
    return geographic.title() if geographic else "Unknown"


def build_job_record(job: Job, search_run_at: str) -> dict[str, str | int]:
    compensation = analyze_compensation_and_hours(job.text_blob(), job.salary)
    return {
        "search_run_at": search_run_at,
        "score": job.relevance_score,
        "title_fit_score": job.title_fit_score,
        "seniority_fit_score": job.seniority_fit_score,
        "remote_fit_score": job.remote_fit_score,
        "skill_fit_score": job.skill_fit_score,
        "geography_fit_score": job.geography_fit_score,
        "compensation_fit_score": job.compensation_fit_score,
        "company_fit_score": job.company_fit_score,
        "penalty_score": job.penalty_score,
        "priority": job.priority_level,
        "title": job.job_title,
        "company": job.company_name or "Unknown",
        "company_fit": job.company_fit or "unknown",
        "company_size": job.company_size or "unknown",
        "company_size_source": job.company_size_source or "",
        "location": display_location(job),
        "city": job.city or "Unknown",
        "country": job.country or "Unknown",
        "region": job.region or "Unknown",
        "remote_type": job.remote_type,
        "seniority": job.seniority,
        "salary": job.salary or "Not listed",
        "salary_found": compensation["salary_found"],
        "salary_target_met": compensation["salary_target_met"],
        "hours_found": compensation["hours_found"],
        "hours_target_met": compensation["hours_target_met"],
        "salary_hour_notes": compensation["salary_hour_notes"],
        "skills": job.required_skills or "Not extracted",
        "description": _shorten(job.job_description, 1200),
        "source": job.source_platform,
        "url": job.job_url,
        "reason": job.reason_for_score,
        "date_found": job.date_found,
        "date_posted": job.date_posted,
        "status": job.application_status,
        "interesting": "",
        "applied": "no",
        "next_step": job.next_step,
        "review_notes": job.review_notes,
        "dismissed": "no",
    }


def build_job_records(jobs: list[Job]) -> list[dict[str, str | int]]:
    search_run_at = datetime.now().astimezone().isoformat(timespec="seconds")
    return [build_job_record(job, search_run_at) for job in jobs]


def _shorten(value: str, limit: int) -> str:
    clean = " ".join((value or "").split())
    if len(clean) <= limit:
        return clean
    return f"{clean[: limit - 1].rstrip()}..."
