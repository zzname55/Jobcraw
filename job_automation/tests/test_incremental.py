from __future__ import annotations

from database.db import JobDatabase
from database.models import Job
from matching.deduplication import prepare_deduplication


def _job(title: str, url: str) -> Job:
    return prepare_deduplication(Job(job_title=title, company_name="Acme", job_url=url, relevance_score=80))


def test_existing_keys_tracks_seen_jobs(tmp_path):
    db = JobDatabase(tmp_path / "jobs.db")
    db.init()
    assert db.existing_keys() == set()  # first run: nothing seen

    first_batch = [_job("AI Automation Specialist", "https://a.test/1"), _job("AI Engineer", "https://a.test/2")]
    db.upsert_jobs(first_batch)

    seen = db.existing_keys()
    assert {job.deduplication_key for job in first_batch} <= seen


def test_new_vs_seen_split_is_incremental(tmp_path):
    db = JobDatabase(tmp_path / "jobs.db")
    db.init()

    run_one = [_job("AI Automation Specialist", "https://a.test/1")]
    db.upsert_jobs(run_one)

    previously_seen = db.existing_keys()  # snapshot before the second run upserts
    run_two = [
        _job("AI Automation Specialist", "https://a.test/1"),  # same posting -> seen
        _job("LLM Automation Engineer", "https://a.test/3"),   # brand new
    ]
    new_jobs = [job for job in run_two if job.deduplication_key not in previously_seen]

    assert len(new_jobs) == 1
    assert new_jobs[0].job_url == "https://a.test/3"
