from __future__ import annotations

from matching.relevance import is_relevant_text
from scrapers.rss_scraper import RssFeedScraper


SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>FlowPilot AI: Senior AI Engineer</title>
    <link>https://example.com/1</link>
    <description>Build AI agent workflows with n8n and LLM tooling.</description>
  </item>
  <item>
    <title>AI Automation Specialist</title>
    <company>AgentStack</company>
    <location>Remote EU</location>
    <link>https://example.com/2</link>
    <description>Automate workflows with n8n.</description>
  </item>
  <item>
    <title>Machine Learning Engineer</title>
    <companyName>Acme ML</companyName>
    <locationRestriction>Anywhere in the World</locationRestriction>
    <link>https://example.com/3</link>
    <description>Build ML systems.</description>
  </item>
  <item>
    <title>KI Spezialist:in (m/w/d)</title>
    <link>https://example.com/4</link>
    <description>KI Automatisierung.</description>
  </item>
  <item>
    <title>Customer Service Agent</title>
    <company>BigCo</company>
    <link>https://example.com/5</link>
    <description>Help customers. We are an AI-powered company.</description>
  </item>
</channel></rss>"""


class DummyResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content


def _scraper(monkeypatch) -> RssFeedScraper:
    scraper = RssFeedScraper(limit=20, feeds=["https://feeds.example/jobs.xml"], rate_limit_seconds=0)
    monkeypatch.setattr(scraper, "get", lambda url, **kw: DummyResponse(SAMPLE_FEED.encode("utf-8")))
    return scraper


def test_rss_extracts_company_from_all_conventions(monkeypatch):
    jobs = _scraper(monkeypatch).search()
    by_url = {job.job_url: job for job in jobs}

    # "Company: Role" title split
    assert by_url["https://example.com/1"].company_name == "FlowPilot AI"
    assert by_url["https://example.com/1"].job_title == "Senior AI Engineer"
    # explicit <company> tag
    assert by_url["https://example.com/2"].company_name == "AgentStack"
    # explicit <companyName> tag (Himalayas style) + locationRestriction
    assert by_url["https://example.com/3"].company_name == "Acme ML"
    assert by_url["https://example.com/3"].location == "Anywhere in the World"


def test_rss_filters_noise_and_handles_german_colon(monkeypatch):
    jobs = _scraper(monkeypatch).search()
    titles = {job.job_title for job in jobs}

    # "Customer Service Agent" must be dropped (bare "agent" is not an AI signal).
    assert all("Customer Service Agent" != job.job_title for job in jobs)
    # German gender form "Spezialist:in" must not be split into a company.
    ki_job = next(job for job in jobs if job.job_url == "https://example.com/4")
    assert ki_job.company_name == ""
    assert ki_job.job_title == "KI Spezialist:in (m/w/d)"
    # Machine Learning roles are relevant again.
    assert "Machine Learning Engineer" in titles


def test_relevance_drops_human_agents_keeps_ai_agents():
    assert not is_relevant_text("Customer Service Agent")
    assert not is_relevant_text("Dental Billing Agent")
    assert is_relevant_text("AI Agent Engineer")
    assert is_relevant_text("Agentic AI Engineer")
    assert is_relevant_text("Machine Learning Engineer")
