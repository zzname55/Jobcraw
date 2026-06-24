from __future__ import annotations

import re

from database.models import Job
from matching.compensation import analyze_compensation_and_hours
from matching.keywords import (
    AI_SKILLS,
    AUTOMATION_SKILLS,
    JUNIOR_SIGNALS,
    OFF_TARGET_TITLE_SIGNALS,
    QA_AUTOMATION_SIGNALS,
    ROLE_TITLE_SIGNALS,
    SENIOR_NEGATIVE_SIGNALS,
    STARTUP_SIGNALS,
    TARGET_TITLES,
    UNRELATED_TITLE_SIGNALS,
)
from matching.relevance import is_relevant_text
from matching.skills import term_in_text


def contains_any(text: str, terms: list[str]) -> bool:
    return any(term_in_text(text, term) for term in terms)


def has_high_experience_requirement(text: str) -> bool:
    lowered = text.lower()
    return bool(re.search(r"\b([5-9]|10)\+?\s*(years|jahre|лет)\b", lowered))


def priority_from_score(score: int) -> str:
    if score >= 80:
        return "urgent"
    if score >= 70:
        return "high"
    if score >= 60:
        return "medium"
    return "low"


def calculate_score_breakdown(job: Job) -> dict[str, int]:
    title = job.job_title.lower()
    text = job.text_blob().lower()
    breakdown = {
        "title_fit_score": 0,
        "seniority_fit_score": 0,
        "remote_fit_score": 0,
        "skill_fit_score": 0,
        "geography_fit_score": 0,
        "compensation_fit_score": 0,
        "company_fit_score": 0,
        "penalty_score": 0,
    }

    title_matches_target = contains_any(title, TARGET_TITLES)
    has_automation = contains_any(text, AUTOMATION_SKILLS)
    has_ai = contains_any(text, AI_SKILLS)

    if title_matches_target:
        breakdown["title_fit_score"] += 25
    if contains_any(title, ROLE_TITLE_SIGNALS):
        breakdown["title_fit_score"] += 5
    if contains_any(text, JUNIOR_SIGNALS):
        breakdown["seniority_fit_score"] += 20
    if job.remote_type in {"remote", "hybrid"} or contains_any(text, ["remote", "hybrid", "homeoffice", "удал"]):
        breakdown["remote_fit_score"] += 15
    if has_automation:
        breakdown["skill_fit_score"] += 15
    if has_ai:
        breakdown["skill_fit_score"] += 15
    if job.region in {"dach", "europe", "worldwide"} or "remote europe" in text:
        breakdown["geography_fit_score"] += 10
    if job.language in {"de", "en", "ru"}:
        breakdown["geography_fit_score"] += 5
    if contains_any(text, STARTUP_SIGNALS) or job.is_startup_likely:
        breakdown["company_fit_score"] += 10

    compensation = analyze_compensation_and_hours(job.text_blob(), job.salary)
    if compensation["salary_target_met"] == "yes":
        breakdown["compensation_fit_score"] += 8
    elif compensation["salary_target_met"] == "no":
        breakdown["penalty_score"] -= 15
    else:
        breakdown["penalty_score"] -= 5
    if compensation["hours_target_met"] == "yes":
        breakdown["compensation_fit_score"] += 7
    elif compensation["hours_target_met"] == "no":
        breakdown["penalty_score"] -= 15
    else:
        breakdown["penalty_score"] -= 5

    if contains_any(text, SENIOR_NEGATIVE_SIGNALS):
        breakdown["penalty_score"] -= 30
    if contains_any(title, SENIOR_NEGATIVE_SIGNALS):
        breakdown["penalty_score"] -= 20
    if has_high_experience_requirement(text):
        breakdown["penalty_score"] -= 20
    if job.remote_type == "onsite" and job.region not in {"dach", "europe"}:
        breakdown["penalty_score"] -= 10
    if contains_any(text, QA_AUTOMATION_SIGNALS) and not contains_any(text, AI_SKILLS + AUTOMATION_SKILLS[:8]):
        breakdown["penalty_score"] -= 10
    # The role must read like an AI/automation job in its TITLE, not merely have AI
    # keywords somewhere in the description (e.g. a "Product Support Specialist" or
    # "DevOps Engineer" at an AI company). Otherwise apply a decisive penalty.
    title_is_relevant = title_matches_target or is_relevant_text(job.job_title)
    if not title_is_relevant:
        breakdown["penalty_score"] -= 45
    if not title_matches_target and contains_any(title, OFF_TARGET_TITLE_SIGNALS):
        breakdown["penalty_score"] -= 20
    if not contains_any(title, ROLE_TITLE_SIGNALS):
        breakdown["penalty_score"] -= 25
    if contains_any(title, UNRELATED_TITLE_SIGNALS):
        breakdown["penalty_score"] -= 100

    return breakdown


def calculate_relevance_score(job: Job) -> int:
    breakdown = calculate_score_breakdown(job)
    return max(0, min(100, sum(breakdown.values())))


def apply_score_breakdown(job: Job) -> Job:
    breakdown = calculate_score_breakdown(job)
    for field, value in breakdown.items():
        setattr(job, field, value)
    job.relevance_score = max(0, min(100, sum(breakdown.values())))
    return job


def classify_company_fit(job: Job) -> str:
    text = job.text_blob().lower()
    if any(term in text for term in ["enterprise", "corporation", "konzern", "10,000+", "10000+"]):
        return "enterprise"
    if any(term in text for term in ["startup", "early-stage", "seed", "series a", "y combinator", "yc"]):
        return "startup"
    if any(term in text for term in ["gmbh", "agency", "agentur", "consulting", "beratung", "saas", "b2b"]):
        return "sme/mid-market"
    return "unknown"


def explain_score(job: Job) -> str:
    text = job.text_blob().lower()
    reasons: list[str] = []
    cautions: list[str] = []

    if contains_any(job.job_title.lower(), TARGET_TITLES):
        reasons.append("title strongly matches an AI automation or applied AI target role")
    if contains_any(text, JUNIOR_SIGNALS):
        reasons.append("junior or entry-level signals were found")
    if job.remote_type in {"remote", "hybrid"}:
        reasons.append(f"{job.remote_type} work is available")
    if contains_any(text, AUTOMATION_SKILLS):
        reasons.append("automation, no-code, or workflow keywords are present")
    if contains_any(text, AI_SKILLS):
        reasons.append("AI, LLM, or agent keywords are present")
    if job.region in {"dach", "europe", "worldwide"}:
        reasons.append("region matches the target geography")

    compensation = analyze_compensation_and_hours(job.text_blob(), job.salary)
    if compensation["salary_target_met"] == "yes":
        reasons.append("compensation target is met")
    if compensation["hours_target_met"] == "yes":
        reasons.append("weekly hours target is met")
    if compensation["salary_target_met"] in {"no", "unknown"}:
        cautions.append(f"compensation status is {compensation['salary_target_met']}")
    if compensation["hours_target_met"] in {"no", "unknown"}:
        cautions.append(f"weekly hours status is {compensation['hours_target_met']}")
    if contains_any(text, SENIOR_NEGATIVE_SIGNALS):
        cautions.append("senior or lead signals reduce the score")
    if has_high_experience_requirement(text):
        cautions.append("more than 5 years of experience are mentioned")

    if not reasons:
        reasons.append("only weak target-role signals were detected")
    message = "; ".join(reasons)
    if cautions:
        message += ". Caveats: " + "; ".join(cautions)
    return message + "."
