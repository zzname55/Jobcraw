from __future__ import annotations

from database.models import Job
from scrapers.base_scraper import BaseScraper


class JoinScraper(BaseScraper):
    source_name = "join"
    base_url = "https://join.com"

    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        self.logger.info("JOIN integration placeholder. Use GenericSearchScraper with Search API or an approved feed.")
        return []
