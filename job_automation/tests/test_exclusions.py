from __future__ import annotations

from database.models import Job
from matching.exclusions import excluded_low_cost_region


def _job(**kw) -> Job:
    base = dict(
        job_title="AI Automation Specialist",
        company_name="Some Co",
        location="Remote",
        job_description="Build automation workflows.",
    )
    base.update(kw)
    return Job(**base)


def test_pkr_salary_is_banned_even_when_location_is_europe():
    # Mirrors the screenshot: a "Spain / Remote" role that pays in PKR.
    job = _job(location="Remote / Spain", salary="100,000 - 250,000 PKR")
    excluded, reason = excluded_low_cost_region(job)
    assert excluded is True
    assert "pkr" in reason.lower()


def test_inr_and_lakh_pay_are_banned():
    assert excluded_low_cost_region(_job(salary="6 LPA"))[0] is False  # "LPA" alone is not matched
    assert excluded_low_cost_region(_job(salary="500000 INR per year"))[0] is True
    assert excluded_low_cost_region(_job(job_description="Salary 12 lakhs per annum."))[0] is True
    assert excluded_low_cost_region(_job(job_description="Budget up to 1 crore."))[0] is True


def test_other_low_wage_currencies_are_banned():
    assert excluded_low_cost_region(_job(salary="50,000 BDT/month"))[0] is True       # Bangladesh
    assert excluded_low_cost_region(_job(salary="300,000 NGN"))[0] is True            # Nigeria
    assert excluded_low_cost_region(_job(job_description="Pay 80,000 naira."))[0] is True
    assert excluded_low_cost_region(_job(salary="₱40,000"))[0] is True               # Philippine peso sign
    assert excluded_low_cost_region(_job(salary="20,000,000 VND"))[0] is True         # Vietnam


def test_low_wage_locations_are_banned():
    assert excluded_low_cost_region(_job(location="Bangalore, India"))[0] is True
    assert excluded_low_cost_region(_job(location="Karachi"))[0] is True
    assert excluded_low_cost_region(_job(job_description="Our team is based in Lahore, Pakistan."))[0] is True
    assert excluded_low_cost_region(_job(location="Dhaka, Bangladesh"))[0] is True
    assert excluded_low_cost_region(_job(location="Manila, Philippines"))[0] is True
    assert excluded_low_cost_region(_job(location="Ho Chi Minh City"))[0] is True
    assert excluded_low_cost_region(_job(location="Nairobi, Kenya"))[0] is True
    assert excluded_low_cost_region(_job(location="Cairo, Egypt"))[0] is True


def test_legitimate_jobs_are_not_banned():
    assert excluded_low_cost_region(_job(location="Remote Germany", salary="55,000 EUR"))[0] is False
    # False-positive guards: "Indiana"/"Indianapolis" must NOT trigger the India ban.
    assert excluded_low_cost_region(_job(location="Indianapolis, Indiana, USA"))[0] is False
    assert excluded_low_cost_region(_job(job_description="We work indoors with great coffee."))[0] is False
    # "PHP" the programming language must NOT be read as the Philippine peso.
    assert excluded_low_cost_region(_job(job_description="Stack: PHP, Laravel, MySQL. Remote EU."))[0] is False
    # Lagos (Portugal) / Alexandria (USA) must not be banned via a bare city name.
    assert excluded_low_cost_region(_job(location="Lagos, Portugal"))[0] is False
    assert excluded_low_cost_region(_job(location="Alexandria, Virginia, USA"))[0] is False
