from __future__ import annotations

from database.models import Job
from scrapers.base_scraper import BaseScraper


class YCJobsScraper(BaseScraper):
    source_name = "yc"
    base_url = "https://www.ycombinator.com/jobs"

    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        self.logger.info(
            "YC Jobs uses a dynamic frontend and changing endpoints. Use GenericSearchScraper or add an official feed/API integration later."
        )
        return []
