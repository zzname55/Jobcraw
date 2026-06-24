from __future__ import annotations

import csv
from pathlib import Path

from database.models import Job
from scrapers.base_scraper import BaseScraper


class ManualSourceScraper(BaseScraper):
    source_name = "manual_source"
    source_type = "manual_import"

    def __init__(self, path: Path | str = "manual_jobs.csv", limit: int = 50) -> None:
        super().__init__(limit=limit)
        self.path = Path(path)

    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        if not self.path.exists():
            self.logger.info("No manual_jobs.csv found. Skipping manual import.")
            return []
        jobs: list[Job] = []
        with self.path.open("r", encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file):
                jobs.append(self.normalize_job(Job(**row)))
                if len(jobs) >= self.limit:
                    break
        return jobs
