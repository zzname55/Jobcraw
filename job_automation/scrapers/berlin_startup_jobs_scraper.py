from __future__ import annotations

from database.models import Job
from scrapers.base_scraper import BaseScraper


class BerlinStartupJobsScraper(BaseScraper):
    source_name = "berlinstartupjobs"
    base_url = "https://berlinstartupjobs.com"

    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        self.logger.info("BerlinStartupJobs placeholder. Integrate only with allowed public endpoints or Search API.")
        return []
