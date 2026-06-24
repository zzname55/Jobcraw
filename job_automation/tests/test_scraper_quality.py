from __future__ import annotations

from scrapers.arbeitnow_scraper import ArbeitnowScraper
from scrapers.base_scraper import clean_field
from scrapers.remoteok_scraper import RemoteOKScraper
from scrapers.weworkremotely_scraper import WeWorkRemotelyScraper
from matching.relevance import is_relevant_text


class DummyResponse:
    def __init__(self, payload=None, content: bytes = b"") -> None:
        self._payload = payload
        self.content = content

    def json(self):
        return self._payload


# ---------------------------------------------------------------- relevance ---

def test_is_relevant_text_matches_ai_and_automation():
    assert is_relevant_text("Junior AI Automation Engineer")
    assert is_relevant_text("We build n8n and LLM agent workflows")
    assert is_relevant_text("KI Automatisierung Werkstudent")


def test_is_relevant_text_rejects_unrelated():
    assert not is_relevant_text("Inbound/Outbound Sales Representative")
    assert not is_relevant_text("Warehouse Operations Associate")
    assert not is_relevant_text("Stellvertretender Werkstattleiter")


def test_is_relevant_text_rejects_generic_automation_without_ai_or_tools():
    # Generic "automation" (DevOps/SRE/industrial) must not qualify on its own.
    assert not is_relevant_text("DevOps Engineer with CI/CD automation and Kubernetes")
    assert not is_relevant_text("Site Reliability Engineer - infrastructure automation")
    assert not is_relevant_text("Industrial automation technician for PLC systems")


# ---------------------------------------------------------------- sanitizer ---

def test_clean_field_strips_replacement_and_control_chars():
    assert clean_field("60.000 " + chr(0xFFFD) + " EUR") == "60.000 EUR"
    assert clean_field("keep" + chr(0) + "me  tidy") == "keepme tidy"
    assert clean_field("") == ""


# ------------------------------------------------------ broad-feed filtering ---

def test_remoteok_keeps_only_relevant_jobs(monkeypatch):
    payload = [
        {"legal": "notice without a position key"},
        {
            "position": "Junior AI Automation Engineer",
            "company": "FlowPilot",
            "location": "Remote",
            "url": "https://remoteok.com/jobs/1",
            "tags": ["ai", "automation", "n8n"],
            "description": "Build AI agent workflows.",
        },
        {
            "position": "Warehouse Associate",
            "company": "BoxCo",
            "location": "Remote",
            "url": "https://remoteok.com/jobs/2",
            "tags": ["logistics"],
            "description": "Pack and ship orders.",
        },
    ]
    scraper = RemoteOKScraper(limit=10, rate_limit_seconds=0)
    monkeypatch.setattr(scraper, "get", lambda url, **kw: DummyResponse(payload=payload))

    jobs = scraper.search()
    titles = {job.job_title for job in jobs}
    assert "Junior AI Automation Engineer" in titles
    assert "Warehouse Associate" not in titles


def test_arbeitnow_keeps_only_relevant_jobs(monkeypatch):
    page_one = {
        "data": [
            {
                "title": "AI Workflow Specialist",
                "company_name": "AgentStack",
                "location": "Berlin",
                "remote": True,
                "url": "https://arbeitnow.com/jobs/1",
                "tags": ["ai", "automation"],
                "description": "<p>LLM automation with n8n.</p>",
            },
            {
                "title": "Stellvertretender Werkstattleiter",
                "company_name": "AutoHaus",
                "location": "Munich",
                "remote": False,
                "url": "https://arbeitnow.com/jobs/2",
                "tags": ["handwerk"],
                "description": "<p>Werkstatt leiten.</p>",
            },
        ]
    }
    calls = {"n": 0}

    def fake_get(url, **kwargs):
        calls["n"] += 1
        return DummyResponse(payload=page_one if calls["n"] == 1 else {"data": []})

    scraper = ArbeitnowScraper(limit=10, rate_limit_seconds=0)
    monkeypatch.setattr(scraper, "get", fake_get)

    jobs = scraper.search()
    titles = {job.job_title for job in jobs}
    assert "AI Workflow Specialist" in titles
    assert "Stellvertretender Werkstattleiter" not in titles


# ------------------------------------------------------------ WWR RSS feed ---

WWR_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>FlowPilot AI: Junior AI Automation Engineer</title>
    <region>Anywhere in the World</region>
    <country>Germany</country>
    <skills>AI, n8n, automation</skills>
    <description>&lt;p&gt;Build AI agent workflows with n8n and MCP servers.&lt;/p&gt;</description>
    <pubDate>Mon, 22 Jun 2026 10:00:00 +0000</pubDate>
    <link>https://weworkremotely.com/remote-jobs/flowpilot-junior-ai-automation-engineer</link>
  </item>
  <item>
    <title>Golf Carts: Inbound/Outbound Sales Representative</title>
    <region>United States</region>
    <country>United States</country>
    <skills>Sales</skills>
    <description>&lt;p&gt;Close deals over the phone.&lt;/p&gt;</description>
    <pubDate>Mon, 22 Jun 2026 09:00:00 +0000</pubDate>
    <link>https://weworkremotely.com/remote-jobs/golf-carts-sales</link>
  </item>
</channel></rss>"""


def test_weworkremotely_rss_parses_and_filters(monkeypatch):
    scraper = WeWorkRemotelyScraper(limit=10, rate_limit_seconds=0)
    monkeypatch.setattr(scraper, "get", lambda url, **kw: DummyResponse(content=WWR_RSS.encode("utf-8")))

    jobs = scraper.search()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.company_name == "FlowPilot AI"
    assert job.job_title == "Junior AI Automation Engineer"
    assert job.job_url.endswith("flowpilot-junior-ai-automation-engineer")
    assert "<p>" not in job.job_description
    assert job.country == "germany"
