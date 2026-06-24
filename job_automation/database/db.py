from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from database.models import Job


JOB_COLUMNS = [
    "id",
    "job_title",
    "company_name",
    "location",
    "city",
    "country",
    "region",
    "remote_type",
    "seniority",
    "language",
    "source_platform",
    "source_type",
    "job_url",
    "date_found",
    "date_posted",
    "job_description",
    "required_skills",
    "preferred_skills",
    "salary",
    "company_stage",
    "company_size",
    "company_size_source",
    "is_startup_likely",
    "relevance_score",
    "priority_level",
    "reason_for_score",
    "application_status",
    "normalized_title",
    "normalized_company",
    "deduplication_key",
    "created_at",
    "updated_at",
]


class JobDatabase:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def init(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_title TEXT,
                    company_name TEXT,
                    location TEXT,
                    city TEXT,
                    country TEXT,
                    region TEXT,
                    remote_type TEXT,
                    seniority TEXT,
                    language TEXT,
                    source_platform TEXT,
                    source_type TEXT,
                    job_url TEXT,
                    date_found TEXT,
                    date_posted TEXT,
                    job_description TEXT,
                    required_skills TEXT,
                    preferred_skills TEXT,
                    salary TEXT,
                    company_stage TEXT,
                    company_size TEXT,
                    company_size_source TEXT,
                    is_startup_likely INTEGER,
                    relevance_score INTEGER,
                    priority_level TEXT,
                    reason_for_score TEXT,
                    application_status TEXT,
                    normalized_title TEXT,
                    normalized_company TEXT,
                    deduplication_key TEXT UNIQUE,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            self._ensure_column(connection, "city", "TEXT")
            self._ensure_column(connection, "company_size", "TEXT")
            self._ensure_column(connection, "company_size_source", "TEXT")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(relevance_score)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_region ON jobs(region)")

    def _ensure_column(self, connection: sqlite3.Connection, column: str, column_type: str) -> None:
        existing = {row["name"] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()}
        if column not in existing:
            connection.execute(f"ALTER TABLE jobs ADD COLUMN {column} {column_type}")

    def upsert_jobs(self, jobs: Iterable[Job]) -> int:
        rows = 0
        columns = [column for column in JOB_COLUMNS if column != "id"]
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(
            f"{column}=excluded.{column}"
            for column in columns
            if column not in {"created_at", "job_url", "deduplication_key"}
        )
        sql = f"""
            INSERT INTO jobs ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(deduplication_key) DO UPDATE SET {updates}
        """
        with self.connect() as connection:
            for job in jobs:
                record = job.to_record()
                values = [int(record[column]) if column == "is_startup_likely" else record[column] for column in columns]
                connection.execute(sql, values)
                rows += 1
        return rows

    def fetch_jobs(self, min_score: int = 0) -> list[Job]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs WHERE relevance_score >= ? ORDER BY relevance_score DESC, date_found DESC",
                (min_score,),
            ).fetchall()
        return [Job(**dict(row)) for row in rows]

    def update_status(self, job_id: int, status: str) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE jobs SET application_status = ? WHERE id = ?", (status, job_id))
