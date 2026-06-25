from __future__ import annotations

from database.models import Job
from matching.deduplication import collapse_near_duplicates, deduplicate_jobs, prepare_deduplication, title_core


def _job(title: str, company: str, url: str = "", description: str = "", location: str = "Germany") -> Job:
    return prepare_deduplication(Job(job_title=title, company_name=company, job_url=url, job_description=description, location=location))


def test_collapse_merges_gender_variants():
    jobs = [
        _job("(Junior) AI Automation Specialist (m/f/d)", "TeleClinic", "https://a.test/1"),
        _job("(Junior) AI Automation Specialist (m/w/d)", "TeleClinic", "https://a.test/2"),
    ]
    collapsed = collapse_near_duplicates(jobs)
    assert len(collapsed) == 1


def test_collapse_merges_trailing_connector_company_variant():
    jobs = [
        _job("AI Automation Engineer (Junior / Entry Level)", "Vetaion GmbH", "https://a.test/1"),
        _job("AI Automation Engineer Junior Entry Level", "Vetaion GmbH in", "https://b.test/2"),
    ]
    collapsed = collapse_near_duplicates(jobs)
    assert len(collapsed) == 1


def test_collapse_keeps_richer_record_and_backfills():
    jobs = [
        _job("AI Automation Specialist", "Unknown", "https://a.test/1", description="short"),
        _job("AI Automation Specialist", "Acme AI", "https://b.test/2", description="a much longer description here"),
    ]
    collapsed = collapse_near_duplicates(jobs)
    assert len(collapsed) == 1
    assert collapsed[0].company_name == "Acme AI"  # the known, richer record wins


def test_collapse_does_not_merge_genuinely_different_roles():
    jobs = [
        _job("AI Automation Specialist", "Acme", "https://a.test/1"),
        _job("Senior Backend Engineer", "Acme", "https://a.test/2"),
    ]
    assert len(collapse_near_duplicates(jobs)) == 2


def test_deduplicate_jobs_runs_collapse_pass():
    jobs = [
        Job(job_title="AI Automation Specialist (m/f/d)", company_name="TeleClinic", job_url="https://a.test/1"),
        Job(job_title="AI Automation Specialist (m/w/d)", company_name="TeleClinic", job_url="https://a.test/2"),
    ]
    assert len(deduplicate_jobs(jobs)) == 1


def test_title_core_strips_markers():
    assert title_core("junior ai automation specialist m w d remote") == "ai automation specialist"
