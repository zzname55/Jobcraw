from __future__ import annotations

import config
from matching import company_intel
from matching.company_intel import exceeds_employee_limit, lookup_company_size, parse_headcount_text
from scrapers.join_scraper import JoinScraper


def _use_overrides(monkeypatch, mapping):
    monkeypatch.setattr(company_intel, "_company_size_overrides", lambda: mapping)


def test_lookup_normalizes_name_and_ignores_legal_suffix(monkeypatch):
    _use_overrides(monkeypatch, {"siemens energy": "90000"})
    # "Siemens Energy GmbH" -> normalized "siemens energy" -> matched; 90000 -> bucket.
    label, source = lookup_company_size("Siemens Energy GmbH")
    assert source == "size override file"
    assert exceeds_employee_limit(label) is True


def test_lookup_range_label_keeps_small_company(monkeypatch):
    _use_overrides(monkeypatch, {"acme": "11-50"})
    label, _ = lookup_company_size("Acme Inc")
    assert label == "11-50"
    assert exceeds_employee_limit(label) is False


def test_lookup_returns_none_when_absent(monkeypatch):
    _use_overrides(monkeypatch, {"acme": "10"})
    assert lookup_company_size("Unknown Co") is None
    assert lookup_company_size("") is None


def test_parse_headcount_text():
    assert parse_headcount_text("We are 11-50 employees") == "11-50"
    assert parse_headcount_text("Over 500+ employees worldwide") == "500+"
    assert parse_headcount_text("no headcount here") == ""


class _FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


def test_join_company_headcount_opt_in(monkeypatch):
    monkeypatch.setattr(config, "JOIN_FETCH_COMPANY_SIZE", True)
    scraper = JoinScraper(limit=2, rate_limit_seconds=0)
    monkeypatch.setattr(scraper, "get", lambda url, **kw: _FakeResponse(200, "<p>11-50 employees</p>"))

    assert scraper._company_headcount("https://join.com/companies/acme") == "11-50"
    # second call is served from the per-run cache (no second fetch needed)
    assert scraper._company_headcount("https://join.com/companies/acme") == "11-50"


def test_join_company_headcount_off_by_default(monkeypatch):
    monkeypatch.setattr(config, "JOIN_FETCH_COMPANY_SIZE", False)
    scraper = JoinScraper(limit=2, rate_limit_seconds=0)
    assert scraper._company_headcount("https://join.com/companies/acme") == ""
