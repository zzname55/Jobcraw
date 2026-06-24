from database.models import Job
from matching.deduplication import deduplicate_jobs, normalize_url


def test_tracking_parameters_removed():
    assert normalize_url("https://example.com/job?utm_source=x&ref=y&id=1") == "https://example.com/job?id=1"


def test_duplicate_url_removed():
    jobs = [
        Job(job_title="Junior AI Engineer", company_name="Acme", job_url="https://example.com/job?utm_source=x"),
        Job(job_title="Junior AI Engineer", company_name="Acme GmbH", job_url="https://example.com/job"),
    ]
    assert len(deduplicate_jobs(jobs)) == 1
