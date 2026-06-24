from matching.scorer import calculate_relevance_score, priority_from_score
from scrapers.mock_website_scraper import MockWebsiteScraper


def test_mock_source_scores_good_and_bad_jobs():
    jobs = MockWebsiteScraper(limit=5).search(region="europe", remote=True)
    scored = {job.job_title: calculate_relevance_score(job) for job in jobs}

    assert scored["Junior AI Automation Specialist"] >= 80
    assert scored["MCP Integration Engineer"] >= 70
    assert scored["AI Workflow Specialist"] < scored["Junior AI Automation Specialist"]
    assert scored["Senior QA Automation Engineer"] < 50
    assert scored["Graphic Designer - AI Content"] == 0
    assert priority_from_score(scored["Junior AI Automation Specialist"]) == "urgent"
