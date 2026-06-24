from __future__ import annotations

import logging

from config import GOOGLE_SHEETS_CREDENTIALS_PATH, GOOGLE_SHEETS_ENABLED, GOOGLE_SHEETS_ID
from database.models import Job


def export_to_google_sheets(jobs: list[Job]) -> bool:
    if not GOOGLE_SHEETS_ENABLED:
        return False
    if not GOOGLE_SHEETS_CREDENTIALS_PATH or not GOOGLE_SHEETS_ID:
        logging.getLogger(__name__).warning("Google Sheets export enabled, but credentials path or sheet id is missing.")
        return False
    logging.getLogger(__name__).info("Google Sheets export placeholder received %s jobs.", len(jobs))
    return False
