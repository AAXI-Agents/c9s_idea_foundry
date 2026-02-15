"""Tests for the website search tool factory."""

from unittest.mock import patch


def test_create_website_search_tool_no_url():
    """Without a URL, the tool should search across any site."""
    with patch(
        "crewai_productfeature_planner.tools.website_search_tool.WebsiteSearchTool"
    ) as MockWS:
        MockWS.return_value = "mock_ws_tool"

        from crewai_productfeature_planner.tools.website_search_tool import (
            create_website_search_tool,
        )

        tool = create_website_search_tool()

    MockWS.assert_called_once_with()
    assert tool == "mock_ws_tool"


def test_create_website_search_tool_with_url():
    """With a URL, the tool should be restricted to that site."""
    with patch(
        "crewai_productfeature_planner.tools.website_search_tool.WebsiteSearchTool"
    ) as MockWS:
        MockWS.return_value = "mock_ws_tool_scoped"

        from crewai_productfeature_planner.tools.website_search_tool import (
            create_website_search_tool,
        )

        tool = create_website_search_tool(website="https://example.com")

    MockWS.assert_called_once_with(website="https://example.com")
    assert tool == "mock_ws_tool_scoped"
