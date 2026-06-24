from __future__ import annotations

from database.models import Job
from scrapers.base_scraper import BaseScraper


class WellfoundScraper(BaseScraper):
    source_name = "wellfound"
    base_url = "https://wellfound.com"

    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        self.logger.info("Wellfound is intentionally left as a placeholder. Prefer approved APIs, feeds, or manual import.")
        return []
