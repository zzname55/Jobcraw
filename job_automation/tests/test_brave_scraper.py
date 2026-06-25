from __future__ import annotations

import config
from scrapers.generic_search_scraper import BraveSearchScraper


class _FakeResponse:
    def __init__(self, payload) -> None:
        self._payload = payload

    def json(self):
        return self._payload


BRAVE_PAYLOAD = {
    "web": {
        "results": [
            {
                "title": "Junior AI Automation Specialist at FlowPilot AI",
                "url": "https://flowpilot.ai/careers/1",
                "description": "Build AI agent workflows with n8n. Junior. Remote.",
            },
            {
                "title": "AI Automation Specialist Jobs, Employment | Indeed",
                "url": "https://www.indeed.com/jobs?q=ai",
                "description": "aggregator listing page",
            },
        ]
    }
}


def test_brave_parses_results_and_filters_noise(monkeypatch):
    monkeypatch.setattr(config, "BRAVE_SEARCH_API_KEY", "test-key")
    scraper = BraveSearchScraper(limit=1, rate_limit_seconds=0)
    scraper.validate_links = False  # keep this unit test offline (no HEAD requests)
    monkeypatch.setattr(scraper, "get", lambda url, **kw: _FakeResponse(BRAVE_PAYLOAD))

    jobs = scraper.search(region="europe", remote=True)

    assert any(job.company_name == "FlowPilot AI" for job in jobs)
    assert all("indeed" not in job.job_url for job in jobs)
    assert all(job.source_type == "search_free" for job in jobs)


def test_brave_without_key_is_noop(monkeypatch):
    monkeypatch.setattr(config, "BRAVE_SEARCH_API_KEY", "")
    assert BraveSearchScraper(limit=2, rate_limit_seconds=0).search() == []


def test_brave_to_organic_handles_empty_payload():
    assert BraveSearchScraper._brave_to_organic({}) == []
    assert BraveSearchScraper._brave_to_organic({"web": {}}) == []
