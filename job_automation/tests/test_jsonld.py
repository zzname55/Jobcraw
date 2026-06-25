from __future__ import annotations

import json

from scrapers.jsonld import extract_job_posting, job_posting_fields


def _page(posting) -> str:
    return f'<html><head><script type="application/ld+json">{json.dumps(posting)}</script></head><body>x</body></html>'


POSTING = {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    "title": "AI Automation Engineer &amp; Workflow Builder",
    "datePosted": "2026-05-01T00:00:00Z",
    "hiringOrganization": {"@type": "Organization", "name": "Vetaion GmbH"},
    "jobLocation": {"@type": "Place", "address": {"addressLocality": "Garching", "addressCountry": "Germany"}},
    "description": "&lt;p&gt;Build <b>AI</b> automation with n8n.&lt;/p&gt;",
    "baseSalary": {"@type": "MonetaryAmount", "currency": "EUR", "value": {"minValue": 55000, "maxValue": 70000, "unitText": "YEAR"}},
}


def test_extract_and_flatten_jobposting():
    posting = extract_job_posting(_page(POSTING))
    assert posting is not None
    fields = job_posting_fields(posting)
    assert fields["company"] == "Vetaion GmbH"
    assert fields["location"] == "Garching, Germany"
    assert "&amp;" not in fields["title"] and "&" in fields["title"]
    assert "n8n" in fields["description"] and "<p>" not in fields["description"]
    assert "EUR" in fields["salary"] and "55000" in fields["salary"]


def test_extract_handles_graph_and_type_list():
    page = _page({"@graph": [{"@type": "WebPage"}, {**POSTING, "@type": ["JobPosting", "Thing"]}]})
    posting = extract_job_posting(page)
    assert posting is not None
    assert job_posting_fields(posting)["company"] == "Vetaion GmbH"


def test_extract_returns_none_without_jobposting():
    assert extract_job_posting("<html><body>no structured data</body></html>") is None
    assert extract_job_posting('<script type="application/ld+json">{"@type":"WebPage"}</script>') is None


def test_telecommute_location_falls_back_to_remote():
    posting = {"@type": "JobPosting", "title": "X", "jobLocationType": "TELECOMMUTE", "hiringOrganization": {"name": "Acme"}}
    assert job_posting_fields(posting)["location"] == "Remote"
    assert job_posting_fields(posting)["remote_type"] == "remote"
