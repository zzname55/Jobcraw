from __future__ import annotations

import random

import config
from scrapers.http_client import DEFAULT_USER_AGENTS


class PlaywrightNotAvailable(RuntimeError):
    """Raised when JS rendering is requested but disabled or not installed."""


def render_html(
    url: str,
    timeout_ms: int = 20000,
    wait_until: str = "networkidle",
    headless: bool | None = None,
) -> str:
    """Render a JavaScript page with Playwright and return its HTML (Phase 5).

    Opt-in: gated behind ``ENABLE_PLAYWRIGHT``. Use this only for sources whose
    terms of service allow it and that genuinely have no API/feed -- the project
    deliberately prefers official APIs, public feeds and sitemaps (see
    SCRAPER_ROADMAP.md, section 1). A scraper that uses this should still respect
    robots.txt and rate limits.

    Raises ``PlaywrightNotAvailable`` when rendering is disabled or Playwright (or
    its browser binaries) are not installed, so callers can fall back gracefully.
    """
    if not config.ENABLE_PLAYWRIGHT:
        raise PlaywrightNotAvailable("JS rendering is disabled; set ENABLE_PLAYWRIGHT=true to enable it")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise PlaywrightNotAvailable(
            "playwright is not installed: pip install playwright && playwright install chromium"
        ) from error

    use_headless = config.HEADLESS_BROWSER if headless is None else headless
    with sync_playwright() as player:
        browser = player.chromium.launch(headless=use_headless)
        try:
            page = browser.new_page(user_agent=random.choice(DEFAULT_USER_AGENTS))
            page.goto(url, timeout=timeout_ms, wait_until=wait_until)
            return page.content()
        finally:
            browser.close()
