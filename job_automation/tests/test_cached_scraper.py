from __future__ import annotations

import json

from scrapers import generic_search_scraper as gss
from scrapers.generic_search_scraper import CachedSearchScraper


def test_cached_search_replays_captures_offline(tmp_path, monkeypatch):
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    (capture_dir / "00_query.json").write_text(
        json.dumps(
            {
                "query": '"Junior AI Automation Specialist"',
                "data": {
                    "organic_results": [
                        {
                            "title": "Junior AI Automation Specialist at FlowPilot AI",
                            "link": "https://flowpilot.ai/careers/1",
                            "snippet": "Build AI agent workflows with n8n. Junior. Remote.",
                        },
                        {
                            "title": "AI Automation Specialist Jobs, Employment",
                            "link": "https://www.indeed.com/jobs?q=ai",
                            "snippet": "aggregator listing page",
                        },
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(gss, "SERPAPI_CAPTURE_DIR", str(capture_dir))

    scraper = CachedSearchScraper(limit=10, rate_limit_seconds=0)
    assert scraper.fetch_details is False  # fully offline, no detail-page fetches

    jobs = scraper.search()

    # The real posting is parsed; the Indeed listing page is rejected as noise.
    assert any(job.company_name == "FlowPilot AI" for job in jobs)
    assert all("indeed" not in job.job_url for job in jobs)
    assert all(job.source_type == "cached" for job in jobs)


def test_cached_search_without_capture_dir_returns_empty(monkeypatch):
    monkeypatch.setattr(gss, "SERPAPI_CAPTURE_DIR", "")
    assert CachedSearchScraper(limit=5, rate_limit_seconds=0).search() == []
