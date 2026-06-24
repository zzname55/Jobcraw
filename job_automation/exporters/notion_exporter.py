from __future__ import annotations

import logging

from config import NOTION_API_KEY, NOTION_DATABASE_ID, NOTION_ENABLED
from database.models import Job


def export_to_notion(jobs: list[Job]) -> bool:
    if not NOTION_ENABLED:
        return False
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        logging.getLogger(__name__).warning("Notion export enabled, but API key or database id is missing.")
        return False
    logging.getLogger(__name__).info("Notion export placeholder received %s jobs.", len(jobs))
    return False
