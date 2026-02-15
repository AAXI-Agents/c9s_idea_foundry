"""Tests for the search tool factory."""

from unittest.mock import patch


def test_create_search_tool_returns_serper_instance():
    """create_search_tool should return a SerperDevTool instance."""
    with patch(
        "crewai_productfeature_planner.tools.search_tool.SerperDevTool"
    ) as MockSerper:
        MockSerper.return_value = "mock_serper_tool"

        from crewai_productfeature_planner.tools.search_tool import create_search_tool

        tool = create_search_tool()

    MockSerper.assert_called_once()
    assert tool == "mock_serper_tool"
