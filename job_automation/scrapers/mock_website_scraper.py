from __future__ import annotations

from database.models import Job
from scrapers.base_scraper import BaseScraper


class MockWebsiteScraper(BaseScraper):
    source_name = "mock_websites"
    source_type = "mock"

    def search(self, region: str = "worldwide", remote: bool = True) -> list[Job]:
        jobs = [
            Job(
                job_title="Junior AI Automation Specialist",
                company_name="FlowPilot AI",
                location="Remote Germany",
                country="germany",
                region="dach",
                remote_type="remote",
                seniority="junior",
                language="en",
                source_platform=self.source_name,
                source_type=self.source_type,
                job_url="https://mock-jobs.local/flowpilot-ai-automation-specialist",
                job_description=(
                    "Build workflow automation with AI agents, n8n, webhooks, APIs, and MCP server integrations. "
                    "Junior role, 0-2 years experience, 50.000 EUR year, 36 hours per week."
                ),
                required_skills="AI agents, n8n, MCP server, APIs, workflow automation",
                salary="50.000 EUR year",
                is_startup_likely=True,
            ),
            Job(
                job_title="MCP Integration Engineer",
                company_name="AgentStack Labs",
                location="Hybrid Berlin",
                country="germany",
                region="dach",
                remote_type="hybrid",
                seniority="entry_level",
                language="en",
                source_platform=self.source_name,
                source_type=self.source_type,
                job_url="https://mock-jobs.local/agentstack-mcp-integration-engineer",
                job_description=(
                    "Implement Model Context Protocol connectors, agentic systems, LLM tooling, and internal AI workflows. "
                    "Entry level candidates welcome. Compensation 56.000 EUR year, 35 hours weekly."
                ),
                required_skills="Model Context Protocol, LLM, agentic systems, Python, APIs",
                salary="56.000 EUR year",
                is_startup_likely=True,
            ),
            Job(
                job_title="Senior QA Automation Engineer",
                company_name="TestSuite GmbH",
                location="Onsite Munich",
                country="germany",
                region="dach",
                remote_type="onsite",
                seniority="senior",
                language="en",
                source_platform=self.source_name,
                source_type=self.source_type,
                job_url="https://mock-jobs.local/testsuite-senior-qa-automation",
                job_description="Senior QA automation role with Selenium, Cypress, Playwright testing, and 7+ years experience.",
                required_skills="Selenium, Cypress, QA automation",
                salary="70.000 EUR year",
            ),
            Job(
                job_title="AI Workflow Specialist",
                company_name="OpsCraft",
                location="Remote Europe",
                country="",
                region="europe",
                remote_type="remote",
                seniority="junior",
                language="en",
                source_platform=self.source_name,
                source_type=self.source_type,
                job_url="https://mock-jobs.local/opscraft-ai-workflow-specialist",
                job_description=(
                    "Design AI workflow automation for operations teams using Zapier, Make.com, OpenAI, RAG, and CRM integrations. "
                    "Junior applicants welcome. Salary not listed. Full-time 40 hours per week."
                ),
                required_skills="OpenAI, Zapier, Make.com, RAG, CRM automation",
            ),
            Job(
                job_title="Graphic Designer - AI Content",
                company_name="BrandSpark",
                location="Remote",
                region="worldwide",
                remote_type="remote",
                seniority="unknown",
                language="en",
                source_platform=self.source_name,
                source_type=self.source_type,
                job_url="https://mock-jobs.local/brandspark-graphic-designer-ai",
                job_description="Create marketing visuals with AI tools. No automation, agent, MCP, or workflow engineering ownership.",
                required_skills="Graphic design, AI image tools, marketing",
            ),
            Job(
                # Strong role fit, but the company is too large: it must be dropped
                # by the >200 employee filter before scoring/export.
                job_title="AI Automation Engineer",
                company_name="ScaleCorp Enterprise",
                location="Remote Europe",
                region="europe",
                remote_type="remote",
                seniority="junior",
                language="en",
                source_platform=self.source_name,
                source_type=self.source_type,
                job_url="https://mock-jobs.local/scalecorp-ai-automation-engineer",
                job_description=(
                    "Join our enterprise automation team building AI agents, n8n workflows, "
                    "LLM tooling, and MCP server integrations. We are a team of 2,500 employees. "
                    "Junior friendly, 50.000 EUR year, 35 hours per week."
                ),
                required_skills="AI agents, n8n, MCP server, workflow automation",
                salary="50.000 EUR year",
            ),
        ]
        return [self.normalize_job(job) for job in jobs[: self.limit]]
