from database.models import Job
from exporters.docx_exporter import export_jobs_to_docx
from exporters.xlsx_exporter import XLSX_COLUMNS, export_jobs_to_xlsx


def sample_job() -> Job:
    return Job(
        job_title="Junior AI Automation Specialist",
        company_name="Example AI GmbH",
        location="Remote Germany",
        city="Berlin",
        country="germany",
        region="dach",
        remote_type="remote",
        seniority="junior",
        language="en",
        job_url="https://example.com/job",
        job_description="Build workflow automation with AI agents, MCP server integrations, n8n and APIs. Salary 50.000 EUR Jahr, 36 Stunden pro Woche.",
        required_skills="AI agents, MCP server, n8n, APIs",
        salary="50.000 EUR Jahr",
        company_size="11-50",
        company_size_source="posting text",
        relevance_score=88,
        priority_level="urgent",
        reason_for_score="Strong title match, remote, junior and AI automation signals.",
    )


def test_xlsx_export_creates_file(tmp_path):
    path = export_jobs_to_xlsx([sample_job()], tmp_path)
    assert path.exists()
    assert path.suffix == ".xlsx"
    labels = [label for _, label in XLSX_COLUMNS]
    assert "City" in labels
    assert "Country" in labels
    assert "Company Size" in labels


def test_docx_export_creates_file(tmp_path):
    path = export_jobs_to_docx([sample_job()], tmp_path)
    assert path.exists()
    assert path.suffix == ".docx"
