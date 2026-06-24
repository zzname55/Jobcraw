from __future__ import annotations

import json

from main import score_jobs
from matching.deduplication import deduplicate_jobs
from scrapers.ats_scraper import AtsScraper, load_companies


GREENHOUSE_PAYLOAD = {
    "jobs": [
        {
            "title": "Junior AI Automation Engineer",
            "absolute_url": "https://boards.greenhouse.io/flowpilot/jobs/1",
            "updated_at": "2026-06-20T10:00:00Z",
            "location": {"name": "Remote - Germany"},
            "content": "<p>Build <b>workflow automation</b> with AI agents, n8n and MCP servers. Junior role.</p>",
        },
        {
            "title": "Office Manager",
            "absolute_url": "https://boards.greenhouse.io/flowpilot/jobs/2",
            "updated_at": "2026-06-19T10:00:00Z",
            "location": {"name": "Berlin"},
            "content": "<p>Front desk and office operations.</p>",
        },
    ]
}

LEVER_PAYLOAD = [
    {
        "text": "AI Workflow Specialist",
        "hostedUrl": "https://jobs.lever.co/agentstack/abc",
        "applyUrl": "https://jobs.lever.co/agentstack/abc/apply",
        "createdAt": 1718870400000,
        "categories": {"location": "Remote (Europe)", "commitment": "Full-time", "team": "Engineering"},
        "description": "<p>Design AI workflow automation with LLM agents and Zapier.</p>",
    },
    {
        "text": "Account Executive",
        "hostedUrl": "https://jobs.lever.co/agentstack/xyz",
        "categories": {"location": "London"},
        "description": "<p>Close enterprise sales deals.</p>",
    },
]


ASHBY_PAYLOAD = {
    "jobs": [
        {
            "title": "Junior AI Solutions Engineer",
            "location": "Remote - Europe",
            "isRemote": True,
            "jobUrl": "https://jobs.ashbyhq.com/opscraft/abc",
            "publishedAt": "2026-06-18T10:00:00Z",
            "descriptionPlain": "Implement AI agent workflows and LLM tooling for customers.",
        },
        {
            "title": "Office Coordinator",
            "location": "Berlin",
            "isRemote": False,
            "jobUrl": "https://jobs.ashbyhq.com/opscraft/xyz",
            "descriptionPlain": "Coordinate the office.",
        },
    ]
}


WORKABLE_PAYLOAD = {
    "name": "Flowpilot",
    "description": "AI automation startup",
    "jobs": [
        {
            "title": "Junior AI Automation Engineer",
            "city": "Berlin",
            "country": "Germany",
            "workplace_type": "remote",
            "url": "https://apply.workable.com/flowpilot/j/ABC123/",
            "published_on": "2026-06-15",
            "description": "<p>Build AI agent workflows with n8n and LLM tooling.</p>",
        },
        {
            "title": "Office Manager",
            "city": "Berlin",
            "country": "Germany",
            "workplace_type": "on-site",
            "url": "https://apply.workable.com/flowpilot/j/XYZ789/",
            "description": "<p>Run the office.</p>",
        },
    ],
}


def _write_companies(tmp_path, greenhouse=None, lever=None, ashby=None, workable=None):
    path = tmp_path / "companies.yaml"
    lines = ["greenhouse:"]
    for slug in greenhouse or []:
        lines.append(f"  - {slug}")
    lines.append("lever:")
    for slug in lever or []:
        lines.append(f"  - {slug}")
    lines.append("ashby:")
    for slug in ashby or []:
        lines.append(f"  - {slug}")
    lines.append("workable:")
    for slug in workable or []:
        lines.append(f"  - {slug}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _patch_http(scraper, monkeypatch):
    class DummyResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, **kwargs):
        if "greenhouse" in url:
            return DummyResponse(GREENHOUSE_PAYLOAD)
        if "lever" in url:
            return DummyResponse(LEVER_PAYLOAD)
        if "ashby" in url:
            return DummyResponse(ASHBY_PAYLOAD)
        if "workable" in url:
            return DummyResponse(WORKABLE_PAYLOAD)
        return DummyResponse({})

    monkeypatch.setattr(scraper, "get", fake_get)


def test_load_companies_reads_slugs(tmp_path):
    path = _write_companies(tmp_path, greenhouse=["flowpilot"], lever=["agentstack"], ashby=["opscraft"])
    companies = load_companies(path)
    assert companies["greenhouse"] == ["flowpilot"]
    assert companies["lever"] == ["agentstack"]
    assert companies["ashby"] == ["opscraft"]


def test_load_companies_missing_file_returns_empty(tmp_path):
    assert load_companies(tmp_path / "nope.yaml") == {}


def test_ats_scraper_maps_and_filters_jobs(tmp_path, monkeypatch):
    path = _write_companies(tmp_path, greenhouse=["flowpilot"], lever=["agentstack"], ashby=["opscraft"], workable=["flowpilot"])
    scraper = AtsScraper(limit=50, companies_file=path, rate_limit_seconds=0)
    _patch_http(scraper, monkeypatch)

    jobs = scraper.search(region="europe", remote=True)
    titles = {job.job_title for job in jobs}

    # Relevant AI/automation titles are kept; office/sales roles are filtered out.
    assert "Junior AI Automation Engineer" in titles
    assert "AI Workflow Specialist" in titles
    assert "Junior AI Solutions Engineer" in titles  # from Ashby
    assert "Office Manager" not in titles
    assert "Account Executive" not in titles
    assert "Office Coordinator" not in titles  # from Ashby

    ashby_job = next(job for job in jobs if job.source_platform == "ashby:opscraft")
    assert ashby_job.job_url == "https://jobs.ashbyhq.com/opscraft/abc"
    assert ashby_job.remote_type == "remote"

    workable_job = next(job for job in jobs if job.source_platform == "workable:flowpilot")
    assert workable_job.company_name == "Flowpilot"
    assert workable_job.remote_type == "remote"
    assert workable_job.job_url == "https://apply.workable.com/flowpilot/j/ABC123/"

    greenhouse_job = next(job for job in jobs if job.source_platform == "greenhouse:flowpilot")
    assert greenhouse_job.company_name == "Flowpilot"
    assert greenhouse_job.job_url == "https://boards.greenhouse.io/flowpilot/jobs/1"
    # normalize_job enrichment ran (HTML was stripped, skills/region detected).
    assert "<p>" not in greenhouse_job.job_description
    assert greenhouse_job.country == "germany"
    assert greenhouse_job.required_skills

    lever_job = next(job for job in jobs if job.source_platform == "lever:agentstack")
    assert lever_job.job_url == "https://jobs.lever.co/agentstack/abc"


def test_ats_scraper_empty_when_no_slugs(tmp_path):
    path = _write_companies(tmp_path)  # both sections empty
    scraper = AtsScraper(limit=10, companies_file=path, rate_limit_seconds=0)
    assert scraper.search() == []


def test_ats_jobs_flow_through_scoring(tmp_path, monkeypatch):
    path = _write_companies(tmp_path, greenhouse=["flowpilot"])
    scraper = AtsScraper(limit=50, companies_file=path, rate_limit_seconds=0)
    _patch_http(scraper, monkeypatch)

    scored = score_jobs(deduplicate_jobs(scraper.search(region="europe", remote=True)))
    ai_job = next(job for job in scored if job.job_title == "Junior AI Automation Engineer")
    assert ai_job.relevance_score > 0
