from __future__ import annotations

import json

from scrapers.join_scraper import JoinScraper


def _posting_html(posting: dict) -> str:
    block = json.dumps(posting)
    return f'<html><head><script type="application/ld+json">{block}</script></head><body></body></html>'


class _FakeResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text


JUNIOR_POSTING = {
    "@type": "JobPosting",
    "title": "Junior AI Automation &amp; Workflow Engineer (m/w/d)",
    "datePosted": "2026-04-07T06:36:37.929Z",
    "employmentType": "FULL_TIME",
    "hiringOrganization": {"@type": "Organization", "name": "Vetaion GmbH"},
    "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressCountry": "Germany", "addressLocality": "Garching"}},
    "description": "&lt;p&gt;Build AI automation with n8n from 0 to 1.&lt;/p&gt;",
}

OFF_TARGET_POSTING = {
    "@type": "JobPosting",
    "title": "Senior Account Executive",
    "hiringOrganization": {"@type": "Organization", "name": "SalesCo"},
    "jobLocation": {"@type": "Place", "address": {"addressLocality": "Berlin", "addressCountry": "Germany"}},
    "description": "Close deals.",
}


def test_join_parses_jsonld_posting_with_real_company_and_location(monkeypatch):
    scraper = JoinScraper(limit=5, rate_limit_seconds=0)
    monkeypatch.setattr(scraper, "_discover_urls", lambda region="worldwide": ["https://join.com/companies/vetaioncom/16282016-ai"])
    monkeypatch.setattr(scraper, "get", lambda url, **kw: _FakeResponse(200, _posting_html(JUNIOR_POSTING)))

    jobs = scraper.search(region="europe")

    assert len(jobs) == 1
    job = jobs[0]
    # Real hiring organisation, not a guess from the URL slug.
    assert job.company_name == "Vetaion GmbH"
    assert "Garching" in job.location and "Germany" in job.location
    # HTML entities in the title are decoded.
    assert "&amp;" not in job.job_title and "&" in job.job_title
    # Description HTML/entities are flattened to text.
    assert "n8n" in job.job_description and "<p>" not in job.job_description
    assert job.source_platform == "join.com"


def test_join_skips_expired_410_and_off_target_titles(monkeypatch):
    scraper = JoinScraper(limit=5, rate_limit_seconds=0)
    monkeypatch.setattr(
        scraper,
        "_discover_urls",
        lambda region="worldwide": [
            "https://join.com/companies/gone/1-expired",
            "https://join.com/companies/salesco/2-account-executive",
        ],
    )

    def fake_get(url, **kw):
        if "expired" in url:
            return _FakeResponse(410, "gone")
        return _FakeResponse(200, _posting_html(OFF_TARGET_POSTING))

    monkeypatch.setattr(scraper, "get", fake_get)

    # 410 is dropped; the off-target sales role fails the relevance pre-filter.
    assert scraper.search() == []


def test_join_is_posting_url_filters_company_and_landing_pages():
    assert JoinScraper._is_posting_url("https://join.com/companies/acme/123-ai-engineer")
    assert not JoinScraper._is_posting_url("https://join.com/companies/acme")
    assert not JoinScraper._is_posting_url("https://join.com/lp/something")


def test_join_missing_ddgs_library_returns_empty(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "ddgs", None)  # force ImportError on `from ddgs import DDGS`
    assert JoinScraper(limit=3, rate_limit_seconds=0)._discover_urls() == []
