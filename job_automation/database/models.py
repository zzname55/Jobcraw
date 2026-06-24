from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class Job(BaseModel):
    id: int | None = None
    job_title: str = ""
    company_name: str = ""
    location: str = ""
    city: str = ""
    country: str = ""
    region: str = ""
    remote_type: str = "unknown"
    seniority: str = "unknown"
    language: str = "unknown"
    source_platform: str = ""
    source_type: str = "scraper"
    job_url: str = ""
    date_found: str = Field(default_factory=lambda: datetime.now(UTC).date().isoformat())
    date_posted: str = ""
    job_description: str = ""
    required_skills: str = ""
    preferred_skills: str = ""
    salary: str = ""
    company_stage: str = ""
    company_size: str = "unknown"
    company_size_source: str = ""
    is_startup_likely: bool = False
    relevance_score: int = 0
    title_fit_score: int = 0
    seniority_fit_score: int = 0
    remote_fit_score: int = 0
    skill_fit_score: int = 0
    geography_fit_score: int = 0
    compensation_fit_score: int = 0
    company_fit_score: int = 0
    penalty_score: int = 0
    priority_level: str = "low"
    reason_for_score: str = ""
    application_status: str = "new"
    company_fit: str = "unknown"
    review_notes: str = ""
    next_step: str = ""
    normalized_title: str = ""
    normalized_company: str = ""
    deduplication_key: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    def text_blob(self) -> str:
        return " ".join(
            [
                self.job_title,
                self.company_name,
                self.location,
                self.city,
                self.country,
                self.region,
                self.job_description,
                self.required_skills,
                self.preferred_skills,
                self.salary,
                self.company_size,
            ]
        )

    def to_record(self) -> dict[str, Any]:
        if hasattr(self, "model_dump"):
            return self.model_dump()
        return self.dict()
