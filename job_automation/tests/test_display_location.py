from __future__ import annotations

from database.models import Job
from exporters.job_presenter import display_location


def _job(**kw) -> Job:
    base = dict(job_title="AI Automation Specialist", company_name="Some Co")
    base.update(kw)
    return Job(**base)


def test_city_and_country_are_combined():
    assert display_location(_job(city="Berlin", country="germany")) == "Berlin, Germany"


def test_country_only_is_title_cased():
    assert display_location(_job(country="germany", location="Remote Germany")) == "Germany"


def test_work_mode_words_never_appear_as_location():
    # No city/country known -> strip the work-mode word; only "Europe" is a place.
    assert display_location(_job(location="Remote Europe")) == "Europe"
    assert display_location(_job(location="Hybrid DACH")) == "Dach"


def test_pure_remote_or_worldwide_becomes_unknown():
    assert display_location(_job(location="Remote")) == "Unknown"
    assert display_location(_job(location="Hybrid")) == "Unknown"
    assert display_location(_job(location="Worldwide Remote")) == "Unknown"
    assert display_location(_job(location="")) == "Unknown"


def test_unknown_city_country_are_ignored():
    assert display_location(_job(city="Unknown", country="unknown", location="Remote")) == "Unknown"
