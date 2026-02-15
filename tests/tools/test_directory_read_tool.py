"""Tests for the directory read tool factory."""

from unittest.mock import patch


def test_create_directory_read_tool_no_dir():
    """Without a directory, the tool should be un-scoped."""
    with patch(
        "crewai_productfeature_planner.tools.directory_read_tool.DirectoryReadTool"
    ) as MockDir:
        MockDir.return_value = "mock_dir_reader"

        from crewai_productfeature_planner.tools.directory_read_tool import (
            create_directory_read_tool,
        )

        tool = create_directory_read_tool()

    MockDir.assert_called_once_with()
    assert tool == "mock_dir_reader"


def test_create_directory_read_tool_with_dir():
    """With a directory, the tool should be restricted to that path."""
    with patch(
        "crewai_productfeature_planner.tools.directory_read_tool.DirectoryReadTool"
    ) as MockDir:
        MockDir.return_value = "mock_dir_reader_scoped"

        from crewai_productfeature_planner.tools.directory_read_tool import (
            create_directory_read_tool,
        )

        tool = create_directory_read_tool(directory="output/prds")

    MockDir.assert_called_once_with(directory="output/prds")
    assert tool == "mock_dir_reader_scoped"
