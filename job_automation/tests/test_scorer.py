from database.models import Job
from matching.remote_detection import detect_remote_type
from matching.scorer import calculate_relevance_score, priority_from_score


def test_junior_ai_automation_remote_scores_high():
    job = Job(
        job_title="Junior AI Automation Engineer Remote",
        location="Remote Europe",
        region="europe",
        remote_type="remote",
        seniority="junior",
        language="en",
        job_description="Build LLM workflows with OpenAI, n8n, APIs and startup teams.",
    )
    score = calculate_relevance_score(job)
    assert score >= 80
    assert priority_from_score(score) == "urgent"


def test_senior_qa_automation_scores_lower():
    job = Job(
        job_title="Senior QA Automation Engineer",
        location="Onsite USA",
        region="america",
        remote_type="onsite",
        seniority="senior",
        language="en",
        job_description="Selenium test automation, 6+ years experience.",
    )
    assert calculate_relevance_score(job) < 60


def test_remote_type_helper():
    assert detect_remote_type("Werkstudent KI Automatisierung Homeoffice") == "remote"
