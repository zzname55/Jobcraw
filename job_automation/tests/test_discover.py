from __future__ import annotations

from discover_ats_companies import _valid_slug, extract_slug, extract_slugs, merge_into_companies
from scrapers.ats_scraper import load_companies


def test_extract_slug_for_each_ats_shape():
    assert extract_slug("https://boards.greenhouse.io/anthropic/jobs/1") == ("greenhouse", "anthropic")
    assert extract_slug("https://job-boards.greenhouse.io/figma") == ("greenhouse", "figma")
    assert extract_slug("https://boards.greenhouse.io/embed/job_board?for=stripe&t=9") == ("greenhouse", "stripe")
    assert extract_slug("https://jobs.lever.co/spotify/abc") == ("lever", "spotify")
    assert extract_slug("https://jobs.ashbyhq.com/openai/role") == ("ashby", "openai")
    assert extract_slug("https://apply.workable.com/flowpilot/j/ABC/") == ("workable", "flowpilot")
    assert extract_slug("https://acme.workable.com/jobs/1") == ("workable", "acme")


def test_extract_slug_rejects_non_ats_and_invalid():
    assert extract_slug("https://example.com/careers/ai") is None
    assert extract_slug("https://boards.greenhouse.io/") is None
    # URL-encoded spaces are not a real slug
    assert extract_slug("https://jobs.ashbyhq.com/scale%20army%20careers/x") is None


def test_valid_slug():
    assert _valid_slug("hugging-face")
    assert _valid_slug("acme_co")
    assert not _valid_slug("scale%20army")
    assert not _valid_slug("embed")
    assert not _valid_slug("")
    assert not _valid_slug(None)


def test_extract_slugs_aggregates_and_dedups():
    results = [
        {"link": "https://jobs.lever.co/notion/x"},
        {"link": "https://jobs.lever.co/notion/y"},
        {"link": "https://boards.greenhouse.io/ramp/jobs/1"},
        {"link": "https://news.example.com/foo"},
    ]
    found = extract_slugs(results)
    assert sorted(found["lever"]) == ["notion"]
    assert sorted(found["greenhouse"]) == ["ramp"]


def test_merge_into_companies_dedups_against_existing(tmp_path):
    path = tmp_path / "companies.yaml"
    path.write_text("greenhouse:\n  - existing\nlever:\nashby:\nworkable:\n", encoding="utf-8")

    found = {"greenhouse": {"existing", "newco"}, "lever": {"acme"}, "ashby": set(), "workable": set()}
    added = merge_into_companies(path, found)

    assert added["greenhouse"] == ["newco"]  # existing slug is not re-added
    assert added["lever"] == ["acme"]

    result = load_companies(path)
    assert "existing" in result["greenhouse"] and "newco" in result["greenhouse"]
    assert result["lever"] == ["acme"]
