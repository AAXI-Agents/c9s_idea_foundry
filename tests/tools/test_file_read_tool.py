"""Tests for the file read tool factory."""

from unittest.mock import patch, call


def test_create_file_read_tool_no_path():
    """Without a path, the tool should be un-scoped."""
    with patch(
        "crewai_productfeature_planner.tools.file_read_tool.FileReadTool"
    ) as MockRead:
        MockRead.return_value = "mock_reader"

        from crewai_productfeature_planner.tools.file_read_tool import (
            create_file_read_tool,
        )

        tool = create_file_read_tool()

    MockRead.assert_called_once_with()
    assert tool == "mock_reader"


def test_create_file_read_tool_with_path():
    """With a path, the tool should be locked to that file."""
    with patch(
        "crewai_productfeature_planner.tools.file_read_tool.FileReadTool"
    ) as MockRead:
        MockRead.return_value = "mock_reader_scoped"

        from crewai_productfeature_planner.tools.file_read_tool import (
            create_file_read_tool,
        )

        tool = create_file_read_tool(file_path="/tmp/test.md")

    MockRead.assert_called_once_with(file_path="/tmp/test.md")
    assert tool == "mock_reader_scoped"
