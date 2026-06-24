from __future__ import annotations

from database.models import Job
from scrapers.base_scraper import BaseScraper


class GermanTechJobsScraper(BaseScraper):
    source_name = "germantechjobs"
    base_url = "https://germantechjobs.de"

    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        self.logger.info("GermanTechJobs placeholder. Add an approved feed/API parser when available.")
        return []
