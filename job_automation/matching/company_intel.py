from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

import yaml

from config import COMPANY_SIZES_FILE


EMPLOYEE_BUCKETS = [
    (1, 10, "1-10"),
    (11, 50, "11-50"),
    (51, 200, "51-200"),
    (201, 500, "201-500"),
    (501, 1000, "501-1,000"),
    (1001, 5000, "1,001-5,000"),
    (5001, 10000, "5,001-10,000"),
]


def extract_company_size(text: str) -> tuple[str, str]:
    lowered = (text or "").lower()
    range_match = re.search(r"(\d{1,3}(?:,\d{3})?)\s*[-–]\s*(\d{1,3}(?:,\d{3})?)\s+(employees|people|team members)", lowered)
    if range_match:
        start = _to_int(range_match.group(1))
        end = _to_int(range_match.group(2))
        return f"{start:,}-{end:,}", "posting text"

    plus_match = re.search(r"(\d{1,3}(?:,\d{3})?)\+?\s+(employees|people|team members)", lowered)
    if plus_match:
        value = _to_int(plus_match.group(1))
        if "+" in plus_match.group(0):
            return f"{value:,}+", "posting text"
        return _bucket_for(value), "posting text"

    team_match = re.search(r"(team of|team size|company of)\s+(\d{1,4})", lowered)
    if team_match:
        value = int(team_match.group(2))
        return _bucket_for(value), "posting text"

    if any(term in lowered for term in ["enterprise", "corporation", "konzern", "large company"]):
        return "1,001+", "inferred from company wording"
    if any(term in lowered for term in ["startup", "early-stage", "early stage", "seed stage"]):
        return "1-50", "inferred from startup wording"
    if any(term in lowered for term in ["mittelstand", "sme", "small business", "mid-market"]):
        return "51-500", "inferred from SME wording"
    return "unknown", ""


def _to_int(value: str) -> int:
    return int(value.replace(",", ""))


def _bucket_for(value: int) -> str:
    for start, end, label in EMPLOYEE_BUCKETS:
        if start <= value <= end:
            return label
    return "10,001+"


def parse_employee_floor(company_size: str) -> int | None:
    """Return the smallest employee count implied by a company-size label.

    The label comes from ``extract_company_size`` and looks like ``"51-200"``,
    ``"1,001+"`` or ``"unknown"``. We use the lower bound so that a range is only
    rejected when even its smallest possible value is already too large. Returns
    ``None`` when the size is unknown or cannot be parsed.
    """
    text = (company_size or "").strip().lower()
    if not text or text == "unknown":
        return None
    numbers = re.findall(r"\d[\d,]*", text)
    if not numbers:
        return None
    return _to_int(numbers[0])


def _normalize_company_key(name: str) -> str:
    """Lowercase, strip accents/legal suffixes/punctuation for stable matching."""
    text = unicodedata.normalize("NFKD", (name or "").lower()).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for suffix in (" gmbh", " ag", " se", " inc", " llc", " ltd", " bv", " oy", " ab", " co"):
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
    return text


@lru_cache(maxsize=1)
def _company_size_overrides() -> dict[str, str]:
    """Load the curated {normalized company -> size} map once (empty if absent)."""
    try:
        with open(COMPANY_SIZES_FILE, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except (FileNotFoundError, OSError, yaml.YAMLError):
        return {}
    if not isinstance(data, dict):
        return {}
    overrides: dict[str, str] = {}
    for name, value in data.items():
        key = _normalize_company_key(str(name))
        if key:
            overrides[key] = str(value).strip()
    return overrides


def lookup_company_size(company_name: str) -> tuple[str, str] | None:
    """Return (size_label, source) from the curated override file, or None."""
    if not company_name:
        return None
    size = _company_size_overrides().get(_normalize_company_key(company_name))
    if not size:
        return None
    if size.isdigit():  # a bare integer -> normalize to a bucket label
        return _bucket_for(int(size)), "size override file"
    return size, "size override file"


def parse_headcount_text(text: str) -> str:
    """Extract a '1-10' / '11-50' / '500+' headcount label from free page text."""
    lowered = (text or "").lower()
    range_match = re.search(r"(\d[\d.,]*)\s*[-–]\s*(\d[\d.,]*)\s*(?:employees|mitarbeiter)", lowered)
    if range_match:
        return f"{_to_int(range_match.group(1))}-{_to_int(range_match.group(2))}"
    plus_match = re.search(r"(\d[\d.,]*)\+\s*(?:employees|mitarbeiter)", lowered)
    if plus_match:
        return f"{_to_int(plus_match.group(1))}+"
    return ""


def exceeds_employee_limit(company_size: str, limit: int = 200) -> bool:
    """True only when the company is known to have more than ``limit`` employees.

    Unknown or unparseable sizes return ``False`` so that postings without an
    employee count are kept for manual review instead of being silently dropped.
    An open-ended label such as ``"200+"`` is treated as "at least 200, possibly
    more", so it is rejected once the floor reaches the limit.
    """
    text = (company_size or "").strip().lower()
    floor = parse_employee_floor(text)
    if floor is None:
        return False
    if "+" in text:
        return floor >= limit
    return floor > limit
