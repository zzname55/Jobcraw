from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
EXPORT_DIR = DATA_DIR / "exports"
LOG_DIR = DATA_DIR / "logs"
DB_PATH = BASE_DIR / "jobs.db"

load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
SCRAPER_RATE_LIMIT_SECONDS = float(os.getenv("SCRAPER_RATE_LIMIT_SECONDS", "2"))
MAX_JOBS_PER_SOURCE = int(os.getenv("MAX_JOBS_PER_SOURCE", "50"))
DEFAULT_MIN_SCORE = int(os.getenv("DEFAULT_MIN_SCORE", "60"))

# Only target companies under this many employees. Postings from companies that
# are known to exceed this headcount are dropped before scoring and export.
MAX_COMPANY_EMPLOYEES = int(os.getenv("MAX_COMPANY_EMPLOYEES", "200"))

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
BING_SEARCH_API_KEY = os.getenv("BING_SEARCH_API_KEY", "")
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
# Brave Search API (free tier ~2000 queries/month). Used as a key-free-tier
# fallback/complement to DuckDuckGo for resilience against DDG rate-limiting.
BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "")

# Search backend selection (see SCRAPER_ROADMAP.md). "serpapi" uses the paid
# SerpAPI source, "crawler" uses the key-free sources (ATS APIs / feeds), and
# "auto" prefers SerpAPI when a key is set. Currently informational; full
# routing arrives with the discovery loop (roadmap Phase 4).
SEARCH_BACKEND = os.getenv("SEARCH_BACKEND", "auto").lower()

# Default sources when --sources is omitted. The free stack only: no SerpAPI.
# SerpAPI ("generic") is intentionally excluded -- a head-to-head comparison
# showed the free stack matching/beating it, so credits are reserved for the
# occasional ATS discovery run (discover_ats_companies.py). Override via env.
DEFAULT_SOURCES = [
    source.strip()
    for source in os.getenv(
        "DEFAULT_SOURCES",
        "duckduckgo,brave,join,workingnomads,remoteok,remotive,arbeitnow,weworkremotely,ats,hackernews,rss",
    ).split(",")
    if source.strip()
]

# Polite HTTP client knobs (shared by every scraper via scrapers/http_client.py).
HTTP_MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "3"))
HTTP_JITTER_SECONDS = float(os.getenv("HTTP_JITTER_SECONDS", "0.75"))
# Phase 3 politeness hardening.
HTTP_RESPECT_ROBOTS = env_bool("HTTP_RESPECT_ROBOTS", True)
HTTP_ENABLE_CACHE = env_bool("HTTP_ENABLE_CACHE", True)
HTTP_CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("HTTP_CIRCUIT_BREAKER_THRESHOLD", "5"))
# Persist the conditional (ETag/Last-Modified) HTTP cache across runs. Empty to
# disable. Safe to keep: a cached body is only reused on a server 304.
HTTP_CACHE_PATH = os.getenv("HTTP_CACHE_PATH", str(DATA_DIR / "http_cache.json"))

# List of target company ATS slugs for the key-free ATS scraper.
COMPANIES_FILE = Path(os.getenv("COMPANIES_FILE", str(BASE_DIR / "companies.yaml")))

# User-tunable targeting (job titles, off-target signals, search terms per region)
# so the scraper can be retargeted without editing Python. Missing file -> built-in
# defaults are used. See matching/targeting.py.
TARGETING_FILE = Path(os.getenv("TARGETING_FILE", str(BASE_DIR / "targeting.yaml")))

# Curated company -> employee-count overrides so the <200-employee filter actually
# bites for known companies (most postings carry no parseable size). User-editable.
COMPANY_SIZES_FILE = Path(os.getenv("COMPANY_SIZES_FILE", str(BASE_DIR / "company_sizes.yaml")))
# Opt-in: have the join.com scraper fetch each company page for its headcount
# (one extra request per company). Off by default to keep runs fast.
JOIN_FETCH_COMPANY_SIZE = env_bool("JOIN_FETCH_COMPANY_SIZE", False)

# Extra RSS/Atom job feeds for the generic RSS scraper (comma-separated URLs).
# Empty means use the scraper's built-in default feed list.
RSS_FEEDS = [url.strip() for url in os.getenv("RSS_FEEDS", "").split(",") if url.strip()]

# When set, the Generic (SerpAPI) scraper dumps each raw API response to this
# directory. Lets us capture real responses once and iterate on parsing offline
# without spending more SerpAPI credits.
SERPAPI_CAPTURE_DIR = os.getenv("SERPAPI_CAPTURE_DIR", "")

# Whether the Generic scraper fetches each job-detail page for richer text.
# Detail fetches improve quality but add many slow HTTP requests; turn off for
# fast capture runs or when only SerpAPI snippets are needed.
SERPAPI_FETCH_DETAILS = env_bool("SERPAPI_FETCH_DETAILS", True)

GOOGLE_SHEETS_ENABLED = env_bool("GOOGLE_SHEETS_ENABLED", False)
GOOGLE_SHEETS_CREDENTIALS_PATH = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "")

NOTION_ENABLED = env_bool("NOTION_ENABLED", False)
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")

ENABLE_PLAYWRIGHT = env_bool("ENABLE_PLAYWRIGHT", False)
HEADLESS_BROWSER = env_bool("HEADLESS_BROWSER", True)
