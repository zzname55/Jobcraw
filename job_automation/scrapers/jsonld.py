"""Shared schema.org ``JobPosting`` extractor (JSON-LD).

Reading the structured data a site publishes for Google Jobs is far more robust
than guessing a company from a search-result title or scraping CSS selectors:
the JSON-LD format rarely changes and carries the real hiring organisation,
location, salary and dates. Many job pages (join.com, Greenhouse-hosted boards,
company career pages, ...) embed it, so this is a single high-value primitive
used by every scraper that fetches a job-detail page.

The public helpers are deliberately pure (HTML string in, plain dict out) so they
are trivially unit-testable offline.
"""
from __future__ import annotations

import html as html_module
import json
from typing import Any, Iterator

from bs4 import BeautifulSoup


def extract_job_posting(page_html: str) -> dict[str, Any] | None:
    """Return the first ``JobPosting`` object embedded in the page, or ``None``."""
    if not page_html or "JobPosting" not in page_html:
        return None
    soup = BeautifulSoup(page_html, "lxml")
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        if "JobPosting" not in raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for candidate in _iter_objects(data):
            if isinstance(candidate, dict) and _is_job_posting(candidate):
                return candidate
    return None


def job_posting_fields(posting: dict[str, Any]) -> dict[str, str]:
    """Flatten a ``JobPosting`` object into the fields the pipeline cares about."""
    return {
        "title": _clean(html_module.unescape(_first_str(posting.get("title")))),
        "company": _organization_name(posting),
        "location": _location(posting),
        "remote_type": "remote" if str(posting.get("jobLocationType") or "").upper() == "TELECOMMUTE" else "",
        "description": _description(posting),
        "date_posted": _first_str(posting.get("datePosted")),
        "salary": _salary(posting),
    }


def _is_job_posting(obj: dict[str, Any]) -> bool:
    type_value = obj.get("@type")
    if isinstance(type_value, list):
        return "JobPosting" in type_value
    return type_value == "JobPosting"


def _iter_objects(data: Any) -> Iterator[dict[str, Any]]:
    if isinstance(data, list):
        for item in data:
            yield from _iter_objects(item)
    elif isinstance(data, dict):
        yield data
        if "@graph" in data:
            yield from _iter_objects(data["@graph"])


def _organization_name(posting: dict[str, Any]) -> str:
    org = posting.get("hiringOrganization")
    if isinstance(org, dict):
        return _clean(html_module.unescape(_first_str(org.get("name"))))
    return _clean(html_module.unescape(_first_str(org)))


def _location(posting: dict[str, Any]) -> str:
    location = posting.get("jobLocation")
    if isinstance(location, list):
        location = location[0] if location else None
    if isinstance(location, dict):
        address = location.get("address", {})
        if isinstance(address, dict):
            city = address.get("addressLocality") or ""
            country = address.get("addressRegion") or address.get("addressCountry") or ""
            joined = ", ".join(part for part in (str(city).strip(), str(country).strip()) if part)
            if joined:
                return _clean(joined)
    if str(posting.get("jobLocationType") or "").upper() == "TELECOMMUTE":
        return "Remote"
    return ""


def _description(posting: dict[str, Any]) -> str:
    raw = html_module.unescape(_first_str(posting.get("description")))
    if not raw:
        return ""
    text = BeautifulSoup(raw, "lxml").get_text(" ", strip=True)
    return _clean(text)[:7000]


def _salary(posting: dict[str, Any]) -> str:
    base = posting.get("baseSalary")
    if not isinstance(base, dict):
        return ""
    value = base.get("value")
    currency = base.get("currency") or ""
    if isinstance(value, dict):
        low = value.get("minValue") or value.get("value") or ""
        high = value.get("maxValue") or ""
        unit = value.get("unitText") or ""
        amount = "-".join(str(part) for part in (low, high) if part not in ("", None))
        return _clean(" ".join(str(part) for part in (currency, amount, unit) if part))
    if value:
        return _clean(f"{currency} {value}".strip())
    return ""


def _first_str(value: Any) -> str:
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "")


def _clean(value: str) -> str:
    return " ".join((value or "").split())
