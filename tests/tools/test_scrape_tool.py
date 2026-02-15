"""Tests for the web scraping tool factory."""

from unittest.mock import patch


def test_create_scrape_tool_returns_instance():
    """create_scrape_tool should return a ScrapeWebsiteTool instance."""
    with patch(
        "crewai_productfeature_planner.tools.scrape_tool.ScrapeWebsiteTool"
    ) as MockScrape:
        MockScrape.return_value = "mock_scrape_tool"

        from crewai_productfeature_planner.tools.scrape_tool import create_scrape_tool

        tool = create_scrape_tool()

    MockScrape.assert_called_once()
    assert tool == "mock_scrape_tool"
