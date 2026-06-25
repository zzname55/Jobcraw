from __future__ import annotations

from scrapers.workingnomads_scraper import WorkingNomadsScraper


class _FakeResponse:
    def __init__(self, payload) -> None:
        self._payload = payload

    def json(self):
        return self._payload


FEED = [
    {
        "url": "https://www.workingnomads.com/job/1/",
        "title": "AI Automation Engineer",
        "company_name": "FlowPilot",
        "location": "Remote, Europe",
        "tags": ["ai", "automation", "n8n"],
        "description": "<p>Build <b>AI</b> workflow automation.</p>",
        "pub_date": "2026-06-20",
    },
    {
        "url": "https://www.workingnomads.com/job/2/",
        "title": "Senior Account Executive",  # off-target, must be filtered out
        "company_name": "SalesCo",
        "location": "Remote",
        "tags": ["sales"],
        "description": "Close deals with our AI-powered CRM.",
        "pub_date": "2026-06-20",
    },
]


def test_workingnomads_parses_and_filters_on_title(monkeypatch):
    scraper = WorkingNomadsScraper(limit=10, rate_limit_seconds=0)
    monkeypatch.setattr(scraper, "get", lambda url, **kw: _FakeResponse(FEED))

    jobs = scraper.search(region="europe")

    assert len(jobs) == 1
    job = jobs[0]
    assert job.company_name == "FlowPilot"
    assert job.job_title == "AI Automation Engineer"
    assert "<p>" not in job.job_description and "AI workflow" in job.job_description
    assert "n8n" in job.required_skills
    assert job.source_type == "feed"


def test_workingnomads_handles_non_list_payload(monkeypatch):
    scraper = WorkingNomadsScraper(limit=10, rate_limit_seconds=0)
    monkeypatch.setattr(scraper, "get", lambda url, **kw: _FakeResponse({"error": "nope"}))
    assert scraper.search() == []
