from __future__ import annotations

import logging
import random
import time
from urllib.parse import urlparse

import requests


# A small pool of real, current desktop browser User-Agent strings. Rotating
# between honest UA strings is normal courtesy and load-spreading -- it is NOT an
# attempt to defeat an anti-bot system (see SCRAPER_ROADMAP.md, section 1).
DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

# HTTP status codes that are worth retrying with backoff.
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class HttpClient:
    """Polite, shared HTTP client used by every scraper.

    Responsibilities (Phase 0 of SCRAPER_ROADMAP.md):

    - per-host rate limiting with jitter so traffic is paced like a human,
    - retries with exponential backoff on transient errors, honoring ``Retry-After``,
    - a rotating pool of honest User-Agent strings,
    - a reused session / connection pool.

    robots.txt compliance and HTTP caching are intentionally deferred to Phase 3;
    the hooks live here so they can be added without touching the scrapers.
    """

    def __init__(
        self,
        rate_limit_seconds: float = 2.0,
        jitter_seconds: float = 0.75,
        max_retries: int = 3,
        backoff_base: float = 1.5,
        timeout: float = 20.0,
        user_agents: list[str] | None = None,
        session: requests.Session | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.rate_limit_seconds = rate_limit_seconds
        self.jitter_seconds = jitter_seconds
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.timeout = timeout
        self.user_agents = user_agents or DEFAULT_USER_AGENTS
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Accept": "text/html,application/json,application/rss+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
            }
        )
        self.logger = logger or logging.getLogger("http_client")
        self._last_request_at: dict[str, float] = {}

    def get(self, url: str, **kwargs) -> requests.Response:
        """GET ``url`` with rate limiting and retry/backoff. Returns a 2xx response.

        Keyword arguments are passed through to ``requests`` (``params``, extra
        ``headers``, etc.). A random User-Agent is added unless one is supplied.
        """
        host = self._host(url)
        timeout = kwargs.pop("timeout", self.timeout)
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.setdefault("User-Agent", random.choice(self.user_agents))

        attempt = 0
        while True:
            self._respect_rate_limit(host)
            try:
                response = self.session.get(url, timeout=timeout, headers=headers, **kwargs)
            except requests.RequestException as error:
                if attempt >= self.max_retries:
                    raise
                self.logger.info("retrying %s after error: %s", url, error)
                self._sleep_backoff(attempt)
                attempt += 1
                continue

            if response.status_code in RETRY_STATUS_CODES and attempt < self.max_retries:
                self.logger.info("retrying %s after status %s", url, response.status_code)
                self._sleep_backoff(attempt, response)
                attempt += 1
                continue

            response.raise_for_status()
            return response

    def respect_rate_limit(self, url: str = "") -> None:
        """Backward-compatible hook kept for existing scrapers."""
        self._respect_rate_limit(self._host(url))

    def _host(self, url: str) -> str:
        return urlparse(url).netloc.lower()

    def _respect_rate_limit(self, host: str) -> None:
        if self.rate_limit_seconds <= 0:
            return
        last = self._last_request_at.get(host)
        now = time.monotonic()
        if last is not None:
            wait = self.rate_limit_seconds - (now - last)
            if self.jitter_seconds:
                wait += random.uniform(0, self.jitter_seconds)
            if wait > 0:
                time.sleep(wait)
        self._last_request_at[host] = time.monotonic()

    def _sleep_backoff(self, attempt: int, response: requests.Response | None = None) -> None:
        delay = self.backoff_base ** attempt
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    delay = max(delay, float(retry_after))
                except ValueError:
                    pass
        if self.jitter_seconds:
            delay += random.uniform(0, self.jitter_seconds)
        time.sleep(delay)
