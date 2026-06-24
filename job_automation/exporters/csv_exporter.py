from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from config import EXPORT_DIR
from database.models import Job


CSV_COLUMNS = [
    "relevance_score",
    "title_fit_score",
    "seniority_fit_score",
    "remote_fit_score",
    "skill_fit_score",
    "geography_fit_score",
    "compensation_fit_score",
    "company_fit_score",
    "penalty_score",
    "priority_level",
    "job_title",
    "company_name",
    "company_fit",
    "company_size",
    "company_size_source",
    "location",
    "city",
    "country",
    "region",
    "remote_type",
    "seniority",
    "language",
    "source_platform",
    "job_url",
    "reason_for_score",
    "date_found",
    "date_posted",
    "salary",
    "application_status",
]


def export_jobs_to_csv(jobs: list[Job], export_dir: Path = EXPORT_DIR) -> Path:
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / f"jobs_export_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
    frame = pd.DataFrame([job.to_record() for job in jobs])
    if frame.empty:
        frame = pd.DataFrame(columns=CSV_COLUMNS)
    frame = frame.reindex(columns=CSV_COLUMNS)
    frame.to_csv(path, index=False, encoding="utf-8")
    return path
