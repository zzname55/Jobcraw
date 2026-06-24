from scrapers.generic_search_scraper import GenericSearchScraper


def test_generic_search_includes_approved_titles_and_regions():
    scraper = GenericSearchScraper(limit=40)
    queries = scraper.build_queries(region="europe", remote=True)
    query_blob = "\n".join(queries)
    assert '"Junior AI Automation Specialist"' in query_blob
    assert '"MCP Integration Engineer"' in query_blob
    assert '"Remote Europe"' in query_blob
    assert '"Hybrid Europe"' in query_blob
    assert '"Junior AI Automation Specialist" "Germany"' in query_blob
