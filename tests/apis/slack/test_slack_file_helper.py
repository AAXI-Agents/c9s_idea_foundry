"""Tests for _slack_file_helper.py — truncation + file upload fallback.

Covers:
- truncate_with_file_hint() — short content passes through, long content truncated
- upload_content_file() — success, no client, exception
- was_truncated flag for all block builders
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ====================================================================
# truncate_with_file_hint
# ====================================================================


class TestTruncateWithFileHint:
    """Unit tests for the truncation helper."""

    def test_short_content_unchanged(self):
        from crewai_productfeature_planner.apis.slack._slack_file_helper import (
            truncate_with_file_hint,
        )

        preview, was_truncated = truncate_with_file_hint("short text")
        assert preview == "short text"
        assert was_truncated is False

    def test_exact_limit_unchanged(self):
        from crewai_productfeature_planner.apis.slack._slack_file_helper import (
            truncate_with_file_hint,
        )

        text = "a" * 2800
        preview, was_truncated = truncate_with_file_hint(text)
        assert preview == text
        assert was_truncated is False

    def test_over_limit_truncates(self):
        from crewai_productfeature_planner.apis.slack._slack_file_helper import (
            truncate_with_file_hint,
        )

        text = "a" * 5000
        preview, was_truncated = truncate_with_file_hint(text)
        assert was_truncated is True
        assert preview.startswith("a" * 2800)
        assert "2200 more chars" in preview
        assert "attached file" in preview

    def test_custom_limit(self):
        from crewai_productfeature_planner.apis.slack._slack_file_helper import (
            truncate_with_file_hint,
        )

        text = "b" * 300
        preview, was_truncated = truncate_with_file_hint(text, limit=100)
        assert was_truncated is True
        assert preview.startswith("b" * 100)
        assert "200 more chars" in preview


# ====================================================================
# upload_content_file
# ====================================================================


class TestUploadContentFile:
    """Unit tests for the file upload helper."""

    @patch(
        "crewai_productfeature_planner.tools.slack_tools._get_slack_client"
    )
    def test_successful_upload(self, mock_get_client):
        from crewai_productfeature_planner.apis.slack._slack_file_helper import (
            upload_content_file,
        )

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        result = upload_content_file(
            "C123", "ts123", "Full content here", "file.md", "My File"
        )

        assert result is True
        mock_client.files_upload_v2.assert_called_once()
        call_kwargs = mock_client.files_upload_v2.call_args[1]
        assert call_kwargs["channel"] == "C123"
        assert call_kwargs["thread_ts"] == "ts123"
        assert call_kwargs["content"] == "Full content here"
        assert call_kwargs["filename"] == "file.md"
        assert call_kwargs["title"] == "My File"

    @patch(
        "crewai_productfeature_planner.tools.slack_tools._get_slack_client"
    )
    def test_no_thread_ts(self, mock_get_client):
        from crewai_productfeature_planner.apis.slack._slack_file_helper import (
            upload_content_file,
        )

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        result = upload_content_file("C123", None, "content", "f.md", "T")

        assert result is True
        call_kwargs = mock_client.files_upload_v2.call_args[1]
        assert "thread_ts" not in call_kwargs

    @patch(
        "crewai_productfeature_planner.tools.slack_tools._get_slack_client"
    )
    def test_no_client_returns_false(self, mock_get_client):
        from crewai_productfeature_planner.apis.slack._slack_file_helper import (
            upload_content_file,
        )

        mock_get_client.return_value = None

        result = upload_content_file("C123", "ts", "content", "f.md", "T")
        assert result is False

    @patch(
        "crewai_productfeature_planner.tools.slack_tools._get_slack_client"
    )
    def test_exception_returns_false(self, mock_get_client):
        from crewai_productfeature_planner.apis.slack._slack_file_helper import (
            upload_content_file,
        )

        mock_client = MagicMock()
        mock_client.files_upload_v2.side_effect = RuntimeError("API error")
        mock_get_client.return_value = mock_client

        result = upload_content_file("C123", "ts", "content", "f.md", "T")
        assert result is False


# ====================================================================
# was_truncated flag for flow block builders
# ====================================================================


class TestFlowBlocksTruncationFlag:
    """Verify all 5 block builders return was_truncated correctly."""

    def test_idea_approval_short_not_truncated(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            idea_approval_blocks,
        )

        _, was_truncated = idea_approval_blocks("r1", "Short idea", "Original")
        assert was_truncated is False

    def test_idea_approval_long_truncated(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            idea_approval_blocks,
        )

        _, was_truncated = idea_approval_blocks("r1", "x" * 3000, "Original")
        assert was_truncated is True

    def test_requirements_short_not_truncated(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            requirements_approval_blocks,
        )

        _, was_truncated = requirements_approval_blocks("r1", "Short reqs", 1)
        assert was_truncated is False

    def test_requirements_long_truncated(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            requirements_approval_blocks,
        )

        _, was_truncated = requirements_approval_blocks("r1", "x" * 5000, 1)
        assert was_truncated is True

    def test_manual_refinement_short_not_truncated(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            manual_refinement_prompt_blocks,
        )

        _, was_truncated = manual_refinement_prompt_blocks("r1", "Short", 1)
        assert was_truncated is False

    def test_manual_refinement_long_truncated(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            manual_refinement_prompt_blocks,
        )

        _, was_truncated = manual_refinement_prompt_blocks("r1", "x" * 3000, 1)
        assert was_truncated is True

    def test_exec_summary_feedback_short_not_truncated(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_feedback_blocks,
        )

        _, was_truncated = exec_summary_feedback_blocks("r1", "Short", 1)
        assert was_truncated is False

    def test_exec_summary_feedback_long_truncated(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_feedback_blocks,
        )

        _, was_truncated = exec_summary_feedback_blocks("r1", "x" * 5000, 1)
        assert was_truncated is True

    def test_exec_summary_completion_short_not_truncated(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_completion_blocks,
        )

        _, was_truncated = exec_summary_completion_blocks("r1", "Short", 1)
        assert was_truncated is False

    def test_exec_summary_completion_long_truncated(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_completion_blocks,
        )

        _, was_truncated = exec_summary_completion_blocks("r1", "x" * 5000, 1)
        assert was_truncated is True
