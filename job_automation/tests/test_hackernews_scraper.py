from __future__ import annotations

from scrapers.hackernews_scraper import HackerNewsHiringScraper


SEARCH_RESULT = {
    "hits": [
        {"objectID": "999", "title": "Ask HN: Who wants to be hired? (June 2026)"},
        {"objectID": "123", "title": "Ask HN: Who is hiring? (June 2026)"},
    ]
}

THREAD = {
    "title": "Ask HN: Who is hiring? (June 2026)",
    "children": [
        {
            "text": (
                'FlowPilot AI | <a href="https://flowpilot.ai/jobs">flowpilot.ai</a> | Remote (EU) | '
                "Senior AI Engineer<p>We build AI agent workflows with n8n, LLM tooling and MCP servers. "
                "Looking for someone to own automation end to end.</p>"
            )
        },
        {
            "text": (
                "BoxCo | Berlin, Germany | ONSITE | Warehouse Associate<p>Pack and ship customer orders. "
                "No software involved.</p>"
            )
        },
        {"text": "This is just a meta comment about the thread with no pipe and no job.<p>thanks</p>"},
    ],
}


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def _patch(scraper, monkeypatch):
    def fake_get(url, **kwargs):
        if "search_by_date" in url:
            return DummyResponse(SEARCH_RESULT)
        return DummyResponse(THREAD)

    monkeypatch.setattr(scraper, "get", fake_get)


def test_picks_who_is_hiring_thread_not_who_wants_to_be_hired(monkeypatch):
    scraper = HackerNewsHiringScraper(limit=20, rate_limit_seconds=0)
    _patch(scraper, monkeypatch)
    assert scraper._latest_thread_id() == "123"


def test_parses_relevant_postings_and_filters_noise(monkeypatch):
    scraper = HackerNewsHiringScraper(limit=20, rate_limit_seconds=0)
    _patch(scraper, monkeypatch)

    jobs = scraper.search(region="europe", remote=True)

    # The AI posting is kept; the warehouse job and the meta comment are dropped.
    assert len(jobs) == 1
    job = jobs[0]
    assert job.company_name == "FlowPilot AI"
    assert job.remote_type == "remote"
    assert "engineer" in job.job_title.lower()
    assert job.job_url == "https://flowpilot.ai/jobs"


def test_company_cleanup_strips_markdown_and_investors():
    scraper = HackerNewsHiringScraper(limit=20)
    assert scraper._clean_company("*Scribd") == "Scribd"
    assert scraper._clean_company("NewCo (Backed by Sequoia Capital)") == "NewCo"
    assert scraper._clean_company("Acme (https://acme.com)") == "Acme"


def test_location_ignores_role_and_salary_pieces():
    scraper = HackerNewsHiringScraper(limit=20)
    pieces = ["Senior+ Engineers, Tech Lead", "$175,000 - $300,000", "Berlin, Germany"]
    assert scraper._location(pieces) == "Berlin, Germany"
