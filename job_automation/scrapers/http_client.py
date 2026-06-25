from __future__ import annotations

import atexit
import base64
import json
import logging
import random
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from requests.structures import CaseInsensitiveDict


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


class RobotsDisallowedError(Exception):
    """Raised when a URL is disallowed by the host's robots.txt."""


class CircuitOpenError(Exception):
    """Raised when a host is in cooling-off after repeated failures."""


class HttpClient:
    """Polite, shared HTTP client used by every scraper.

    Phase 0:
    - per-host rate limiting with jitter so traffic is paced like a human,
    - retries with exponential backoff on transient errors, honoring ``Retry-After``,
    - a rotating pool of honest User-Agent strings,
    - a reused session / connection pool.

    Phase 3 (politeness hardening):
    - robots.txt compliance (``respect_robots``): per-host rules are fetched and
      cached; disallowed URLs raise ``RobotsDisallowedError`` instead of being hit.
    - conditional-request caching (``enable_cache``): ETag / Last-Modified are
      remembered and re-sent; a ``304 Not Modified`` reuses the cached response.
    - circuit breaker (``circuit_breaker_threshold``): after that many consecutive
      failures a host is put in cooling-off and further requests raise
      ``CircuitOpenError`` for the rest of the run.
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
        respect_robots: bool = False,
        enable_cache: bool = True,
        circuit_breaker_threshold: int = 5,
        cache_path: Path | str | None = None,
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
        self.respect_robots = respect_robots
        self.enable_cache = enable_cache
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self._robots_agent = "job-automation"
        self._last_request_at: dict[str, float] = {}
        self._robots_cache: dict[str, RobotFileParser | None] = {}
        self._cache: dict[str, dict] = {}
        self._failures: dict[str, int] = {}
        self._circuit_open: set[str] = set()
        # Optional cross-run persistence of the conditional cache (ETag/Last-Modified
        # validators + body). Safe because the server still validates via 304.
        self.cache_path = Path(cache_path) if cache_path else None
        if self.cache_path and self.enable_cache:
            self._load_cache()
            atexit.register(self.save_cache)

    def get(self, url: str, **kwargs) -> requests.Response:
        """GET ``url`` politely. Returns a 2xx (or cached 304) response.

        Keyword arguments are passed through to ``requests`` (``params``, extra
        ``headers``, etc.). A random User-Agent is added unless one is supplied.
        Raises ``CircuitOpenError`` or ``RobotsDisallowedError`` when the request
        is refused before it is sent.
        """
        host = self._host(url)
        bypass_robots = kwargs.pop("bypass_robots", False)
        if host in self._circuit_open:
            raise CircuitOpenError(f"circuit open for {host} after repeated failures")
        # robots.txt governs crawling, not documented/authenticated API endpoints
        # (e.g. SerpAPI disallows /search.json for crawlers). Callers hitting such
        # an API pass bypass_robots=True; HTML page crawling still respects robots.
        if self.respect_robots and not bypass_robots and not self._robots_allows(url):
            raise RobotsDisallowedError(f"robots.txt disallows {url}")

        timeout = kwargs.pop("timeout", self.timeout)
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.setdefault("User-Agent", random.choice(self.user_agents))
        cached = self._cache.get(url) if self.enable_cache else None
        if cached:
            if cached.get("etag"):
                headers.setdefault("If-None-Match", cached["etag"])
            if cached.get("last_modified"):
                headers.setdefault("If-Modified-Since", cached["last_modified"])

        attempt = 0
        while True:
            self._respect_rate_limit(host)
            try:
                response = self.session.get(url, timeout=timeout, headers=headers, **kwargs)
            except requests.RequestException as error:
                if attempt >= self.max_retries:
                    self._record_failure(host)
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

            if cached is not None and response.status_code == 304:
                self._record_success(host)
                # Prefer the in-memory response; fall back to one rebuilt from disk.
                return cached.get("response") or self._reconstruct(cached.get("meta") or {})
            if response.status_code >= 400:
                self._record_failure(host)
                response.raise_for_status()

            self._record_success(host)
            self._store_cache(url, response)
            return response

    def respect_rate_limit(self, url: str = "") -> None:
        """Backward-compatible hook kept for existing scrapers."""
        self._respect_rate_limit(self._host(url))

    # -- internals -----------------------------------------------------------

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

    # -- circuit breaker -----------------------------------------------------

    def _record_failure(self, host: str) -> None:
        self._failures[host] = self._failures.get(host, 0) + 1
        if self.circuit_breaker_threshold and self._failures[host] >= self.circuit_breaker_threshold:
            self._circuit_open.add(host)
            self.logger.warning("circuit opened for %s after %d failures", host, self._failures[host])

    def _record_success(self, host: str) -> None:
        self._failures.pop(host, None)
        self._circuit_open.discard(host)

    # -- conditional-request caching ----------------------------------------

    def _store_cache(self, url: str, response: requests.Response) -> None:
        if not self.enable_cache or response.status_code != 200:
            return
        etag = response.headers.get("ETag")
        last_modified = response.headers.get("Last-Modified")
        if etag or last_modified:
            self._cache[url] = {
                "etag": etag,
                "last_modified": last_modified,
                "response": response,
                "meta": self._serialize_response(response),
            }

    # -- persistent conditional cache ---------------------------------------

    @staticmethod
    def _serialize_response(response: requests.Response) -> dict | None:
        content = getattr(response, "content", None)
        if content is None:  # tolerate lightweight/fake responses without .content
            content = (getattr(response, "text", "") or "").encode("utf-8", "ignore")
        if len(content) > 2_000_000:  # don't bloat the cache file with huge bodies
            return None
        headers = getattr(response, "headers", {}) or {}
        return {
            "status_code": getattr(response, "status_code", 200),
            "content": base64.b64encode(content).decode("ascii"),
            "headers": {key: value for key, value in headers.items() if key.lower() in {"content-type", "etag", "last-modified"}},
            "encoding": getattr(response, "encoding", None),
            "url": getattr(response, "url", ""),
        }

    @staticmethod
    def _reconstruct(meta: dict) -> requests.Response:
        rebuilt = requests.Response()
        rebuilt.status_code = meta.get("status_code", 200)
        rebuilt._content = base64.b64decode(meta["content"]) if meta.get("content") else b""
        rebuilt.headers = CaseInsensitiveDict(meta.get("headers", {}))
        rebuilt.url = meta.get("url", "")
        rebuilt.encoding = meta.get("encoding")
        return rebuilt

    def _load_cache(self) -> None:
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return
        if not isinstance(data, dict):
            return
        for url, entry in data.items():
            if isinstance(entry, dict) and entry.get("meta"):
                self._cache[url] = {"etag": entry.get("etag"), "last_modified": entry.get("last_modified"), "meta": entry["meta"], "response": None}

    def save_cache(self) -> None:
        """Merge this client's conditional cache into the shared file on disk."""
        if not self.cache_path or not self.enable_cache:
            return
        try:
            merged = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if not isinstance(merged, dict):
                merged = {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            merged = {}
        for url, entry in self._cache.items():
            meta = entry.get("meta")
            if meta:
                merged[url] = {"etag": entry.get("etag"), "last_modified": entry.get("last_modified"), "meta": meta}
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.cache_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(merged), encoding="utf-8")
            tmp.replace(self.cache_path)
        except OSError as error:
            self.logger.info("could not persist HTTP cache: %s", error)

    # -- robots.txt ----------------------------------------------------------

    def _robots_allows(self, url: str) -> bool:
        host = self._host(url)
        if host not in self._robots_cache:
            self._robots_cache[host] = self._load_robots(url)
        parser = self._robots_cache[host]
        if parser is None:  # could not load robots.txt -> be permissive
            return True
        try:
            return parser.can_fetch(self._robots_agent, url)
        except Exception:
            return True

    def _load_robots(self, url: str) -> RobotFileParser | None:
        parts = urlparse(url)
        robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
        try:
            response = self.session.get(robots_url, timeout=self.timeout, headers={"User-Agent": self._robots_agent})
        except requests.RequestException:
            return None
        if response.status_code >= 400:
            return None
        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser
