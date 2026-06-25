from __future__ import annotations

import sys
import types

from scrapers.generic_search_scraper import DuckDuckGoSearchScraper


class _FakeDDGS:
    results = [
        {
            "title": "Junior AI Automation Specialist at FlowPilot AI",
            "href": "https://flowpilot.ai/careers/1",
            "body": "Build AI agent workflows with n8n. Junior. Remote.",
        },
        {
            "title": "AI Automation Specialist Jobs, Employment",
            "href": "https://www.indeed.com/jobs?q=ai",
            "body": "aggregator listing page",
        },
    ]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def text(self, query, max_results=10):
        return list(self.results)


def _install_fake_ddgs(monkeypatch):
    module = types.ModuleType("ddgs")
    module.DDGS = _FakeDDGS
    monkeypatch.setitem(sys.modules, "ddgs", module)


def test_duckduckgo_parses_results_and_filters_noise(monkeypatch):
    _install_fake_ddgs(monkeypatch)
    scraper = DuckDuckGoSearchScraper(limit=1, rate_limit_seconds=0)
    scraper.validate_links = False  # keep this unit test offline (no HEAD requests)
    assert scraper.fetch_details is False  # snippet-only, offline

    jobs = scraper.search(region="europe", remote=True)

    # The real posting is parsed; the Indeed listing page is rejected as noise.
    assert any(job.company_name == "FlowPilot AI" for job in jobs)
    assert all("indeed" not in job.job_url for job in jobs)
    assert all(job.source_type == "search_free" for job in jobs)


def test_duckduckgo_missing_library_returns_empty(monkeypatch):
    monkeypatch.setitem(sys.modules, "ddgs", None)  # force ImportError on `from ddgs import DDGS`
    assert DuckDuckGoSearchScraper(limit=2, rate_limit_seconds=0).search() == []
