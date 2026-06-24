from __future__ import annotations

import json
from pathlib import Path

from database.models import Job
from exporters.job_presenter import build_job_records
from main import score_jobs
from matching.compensation import analyze_compensation_and_hours
from matching.deduplication import deduplicate_jobs
from matching.scorer import calculate_relevance_score, calculate_score_breakdown, classify_company_fit
from scrapers.generic_search_scraper import GenericSearchScraper


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "serpapi_cases.json"


class DummyResponse:
    def __init__(self, html: str) -> None:
        self.text = html
        self.headers = {"content-type": "text/html; charset=utf-8"}

    def raise_for_status(self) -> None:
        return None


DETAIL_PAGES = {
    "https://jobs.flowpilot.example/junior-ai-automation-specialist": """
        <html><head><title>Junior AI Automation Specialist at FlowPilot AI</title></head>
        <body>
        <main>
        Remote Germany junior role. Build workflow automation with AI agents, n8n,
        MCP server integrations, REST APIs and webhooks. Salary 50.000 EUR year.
        36 hours per week. Startup SaaS team.
        </main>
        </body></html>
    """,
    "https://careers.agentstack.example/mcp-integration-engineer": """
        <html><head><title>MCP Integration Engineer - AgentStack Labs</title></head>
        <body>Hybrid Berlin. Entry-level Model Context Protocol connectors,
        LLM automation, AI agents, Python APIs. 56.000 EUR year, 35 hours weekly.
        Early-stage B2B SaaS startup.</body></html>
    """,
    "https://careers.mittelstand.example/ai-process-automation-specialist": """
        <html><head><title>AI Process Automation Specialist - Mittelstand GmbH</title></head>
        <body>Hybrid Germany. SME and Mittelstand consulting team. Implement AI process
        automation, n8n workflows, CRM automation and LLM tooling. 54.000 EUR Jahr,
        36 Stunden pro Woche.</body></html>
    """,
}


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def parse_fixture_jobs(monkeypatch) -> list[Job]:
    scraper = GenericSearchScraper(limit=10, rate_limit_seconds=0)

    def fake_get(url: str, **kwargs) -> DummyResponse:
        return DummyResponse(DETAIL_PAGES.get(url, "<html><head></head><body></body></html>"))

    monkeypatch.setattr(scraper, "get", fake_get)
    data = load_fixture()
    return scraper._parse_serpapi_results(data, data["query"])


def test_noise_rejection_blocks_social_search_article_and_salary_pages():
    scraper = GenericSearchScraper(limit=10)
    blocked = [
        ("LinkedIn - Robert Example Profile", "https://www.linkedin.com/in/robert-example"),
        ("AI Automation Specialist Jobs, Employment", "https://www.indeed.com/jobs?q=AI+Automation+Specialist"),
        ("1000+ AI Automation Specialist Jobs Hiring Now", "https://www.ziprecruiter.com/Jobs/AI-Automation-Specialist"),
        ("X post about MCP servers", "https://x.com/example/status/123"),
        ("What does an AI Implementation Specialist do?", "https://careerexplorer.example/ai-implementation-specialist"),
        ("AI Automation Specialist Salary Guide", "https://salary.example/ai-automation-specialist-salary"),
    ]
    assert all(scraper._is_noisy_result(title, url) for title, url in blocked)


def test_live_run_noise_patterns_are_blocked():
    scraper = GenericSearchScraper(limit=10)
    blocked = [
        ("Boyun Wang - Junior AI Agent Engineer specializing in regulated healthcare software | Reval", "https://www.reval.site/u/boyun-wang"),
        ("n8n Community", "https://community.n8n.io/top?page=1&tl=zh_TW"),
        ("Workflow Automation Specialist Career Path, Skills & Advice 2026", "https://jobicy.com/careers/workflow-automation-specialist"),
        ("Remote AI Automation Specialist | From $1,500/mo | Kuubiik", "https://kuubiik.com/services/ai-automation-specialist"),
    ]
    assert all(scraper._is_noisy_result(title, url) for title, url in blocked)


def test_builtin_company_and_title_cleanup_supports_deduplication():
    scraper = GenericSearchScraper(limit=10)
    title = "AI Process Automation Specialist - Duetto | Built In San Francisco"

    assert scraper._guess_company(title, "builtinsf.com") == "Duetto"
    assert scraper._clean_title(title) == "AI Process Automation Specialist - Duetto"


def test_country_subdomain_is_not_used_as_company_name():
    scraper = GenericSearchScraper(limit=10)
    title = "Junior AI Automation Specialist (WhatsApp & Business ..."
    domain = "egypt.tanqeeb.com"

    assert scraper._guess_company(title, domain) == "Unknown"


def test_strong_matches_survive_parsing_and_score_high(monkeypatch):
    jobs = parse_fixture_jobs(monkeypatch)
    scored = {job.job_title: calculate_relevance_score(job) for job in jobs}

    assert scored["Junior AI Automation Specialist at FlowPilot AI"] >= 90
    assert scored["MCP Integration Engineer - AgentStack Labs"] >= 80
    assert scored["AI Process Automation Specialist - Mittelstand GmbH"] >= 80


def test_mismatches_score_low_or_zero(monkeypatch):
    jobs = parse_fixture_jobs(monkeypatch)
    scored = {job.job_title: calculate_relevance_score(job) for job in jobs}

    assert scored["Senior QA Automation Engineer"] < 50
    assert scored["Marketing Automation Manager"] == 0
    assert scored["Data Entry Automation Clerk"] == 0
    assert scored["Robotics Automation Engineer"] == 0
    assert scored["Industrial Automation Technician"] == 0


def test_seniority_penalties_are_strong():
    titles = ["Senior AI Automation Engineer", "Lead AI Automation Engineer", "Principal AI Automation Architect", "Head of AI Automation"]
    for title in titles:
        job = Job(
            job_title=title,
            location="Remote Europe",
            region="europe",
            remote_type="remote",
            language="en",
            job_description="Build AI automation with LLM agents, n8n and APIs. 8+ years experience.",
        )
        assert calculate_relevance_score(job) < 60


def test_compensation_hours_targets_change_score_visibly():
    good = Job(
        job_title="Junior AI Automation Specialist",
        location="Remote Germany",
        region="dach",
        remote_type="remote",
        seniority="junior",
        language="en",
        job_description="AI agents, workflow automation, n8n. 50.000 EUR year, 36 hours per week.",
    )
    low_salary = _copy_job(good, job_description="AI agents, workflow automation, n8n. 3.500 EUR month, 36 hours per week.")
    too_many_hours = _copy_job(good, job_description="AI agents, workflow automation, n8n. 50.000 EUR year, 40 hours per week.")

    assert analyze_compensation_and_hours(good.text_blob(), good.salary)["salary_target_met"] == "yes"
    assert calculate_score_breakdown(good)["compensation_fit_score"] > calculate_score_breakdown(low_salary)["compensation_fit_score"]
    assert calculate_score_breakdown(good)["penalty_score"] > calculate_score_breakdown(low_salary)["penalty_score"]
    assert calculate_score_breakdown(good)["compensation_fit_score"] > calculate_score_breakdown(too_many_hours)["compensation_fit_score"]
    assert calculate_score_breakdown(good)["penalty_score"] > calculate_score_breakdown(too_many_hours)["penalty_score"]


def test_remote_geo_targets_score_higher_than_onsite_usa_only():
    remote_germany = Job(job_title="Junior AI Automation Specialist", location="Remote Germany", region="dach", remote_type="remote", seniority="junior", language="en", job_description="AI agents, n8n, workflow automation. 50.000 EUR year, 36 hours per week.")
    hybrid_berlin = _copy_job(remote_germany, location="Hybrid Berlin", remote_type="hybrid")
    remote_europe = _copy_job(remote_germany, location="Remote Europe", region="europe")
    onsite_usa = _copy_job(remote_germany, location="Onsite USA only", region="america", country="usa", remote_type="onsite")

    assert calculate_relevance_score(remote_germany) >= 80
    assert calculate_relevance_score(hybrid_berlin) >= 80
    assert calculate_relevance_score(remote_europe) >= 80
    assert calculate_relevance_score(onsite_usa) < calculate_relevance_score(remote_germany)


def test_duplicate_roles_across_job_boards_are_removed(monkeypatch):
    jobs = parse_fixture_jobs(monkeypatch)
    flowpilot_jobs = [job for job in jobs if "FlowPilot AI" in job.job_title]
    assert len(flowpilot_jobs) == 3

    unique = deduplicate_jobs(flowpilot_jobs)
    assert len(unique) == 1


def test_company_type_classification_distinguishes_startup_sme_and_enterprise():
    startup = Job(job_title="Junior AI Automation Specialist", company_name="FlowPilot AI", job_description="Early-stage B2B SaaS startup.")
    sme = Job(job_title="AI Process Automation Specialist", company_name="Mittelstand GmbH", job_description="GmbH agency consulting team for SME clients.")
    enterprise = Job(job_title="AI Tooling Engineer", company_name="EnterpriseCorp", job_description="10,000+ employee enterprise corporation.")

    assert classify_company_fit(startup) == "startup"
    assert classify_company_fit(sme) == "sme/mid-market"
    assert classify_company_fit(enterprise) == "enterprise"


def test_query_coverage_for_first_10_20_50_queries():
    queries_10 = "\n".join(GenericSearchScraper(limit=10).build_queries(region="europe", remote=True))
    queries_20 = "\n".join(GenericSearchScraper(limit=20).build_queries(region="europe", remote=True))
    queries_50 = "\n".join(GenericSearchScraper(limit=50).build_queries(region="europe", remote=True))

    assert "Junior AI Automation Specialist" in queries_10
    assert "Junior Workflow Automation Specialist" in queries_10
    assert "n8n Automation Specialist" in queries_20
    assert "AI Agents Specialist" in queries_20
    assert "MCP Server Developer" in queries_20
    assert "workflow automation" in queries_50
    assert "Model Context Protocol" in queries_50
    assert "site:join.com" in queries_50


def test_europe_queries_do_not_start_with_generic_worldwide_remote_terms():
    queries = GenericSearchScraper(limit=7).build_queries(region="europe", remote=True)

    assert all('"Remote"' not in query and '"Hybrid"' not in query for query in queries)
    assert any('"Remote Europe"' in query for query in queries)
    assert any('"Hybrid Europe"' in query for query in queries)


def test_extraction_fills_excel_ready_fields(monkeypatch):
    jobs = parse_fixture_jobs(monkeypatch)
    scored = score_jobs(deduplicate_jobs(jobs))
    records = build_job_records(scored)
    flowpilot = next(record for record in records if record["company"] == "FlowPilot AI")

    assert flowpilot["title_fit_score"] > 0
    assert flowpilot["skill_fit_score"] > 0
    assert flowpilot["remote_type"] == "remote"
    assert flowpilot["location"] == "Remote Germany"
    assert flowpilot["city"] == "Unknown"
    assert flowpilot["country"] == "germany"
    assert flowpilot["company_size"] == "11-50"
    assert flowpilot["salary_target_met"] == "yes"
    assert flowpilot["hours_target_met"] == "yes"
    assert "n8n" in flowpilot["skills"].lower()
    assert flowpilot["dismissed"] == "no"


def _copy_job(job: Job, **updates) -> Job:
    if hasattr(job, "model_copy"):
        return job.model_copy(update=updates)
    return job.copy(update=updates)
