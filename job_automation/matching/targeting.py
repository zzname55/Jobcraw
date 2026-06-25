"""Load user-tunable targeting (titles, off-target signals, search terms).

The lists that decide *what* the scraper looks for live in ``targeting.yaml`` so a
user can retarget the tool (different roles, regions, exclusions) without touching
Python. Any key that is missing or empty falls back to the built-in default passed
by the caller, so deleting the file simply restores the original behaviour.
"""
from __future__ import annotations

from typing import Any

import yaml

from config import TARGETING_FILE


def _load() -> dict[str, Any]:
    try:
        with open(TARGETING_FILE, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except (FileNotFoundError, OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


_DATA = _load()


def get_list(key: str, default: list[str], *, lower: bool = True) -> list[str]:
    """Return the YAML list for ``key`` (cleaned), or ``default`` if absent/empty."""
    value = _DATA.get(key)
    if not isinstance(value, list) or not value:
        return default
    items = [str(item).strip() for item in value if str(item).strip()]
    return [item.lower() for item in items] if lower else items


def get_region_terms(default: dict[str, list[str]]) -> dict[str, list[str]]:
    """Return the region->search-terms mapping from YAML, or ``default``."""
    value = _DATA.get("region_terms")
    if not isinstance(value, dict) or not value:
        return default
    cleaned: dict[str, list[str]] = {}
    for region, terms in value.items():
        if isinstance(terms, list):
            kept = [str(term).strip() for term in terms if str(term).strip()]
            if kept:
                cleaned[str(region).strip().lower()] = kept
    return cleaned or default
