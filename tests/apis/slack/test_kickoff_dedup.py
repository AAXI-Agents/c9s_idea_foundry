"""Tests for kick_off_prd_flow duplicate-idea deduplication.

Verifies that kick_off_prd_flow blocks duplicate ideas before starting
a new flow — both active (inprogress/paused) and recently completed
duplicates should be rejected.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

_MODULE = "crewai_productfeature_planner.apis.slack._flow_handlers"
_WI_MODULE = "crewai_productfeature_planner.mongodb.working_ideas"
_REPLY = "crewai_productfeature_planner.apis.slack._session_reply.reply"
_SLACK_CLIENT = "crewai_productfeature_planner.tools.slack_tools._get_slack_client"


def _call_kickoff(
    idea: str = "add knowledge sharing",
    channel: str = "C123",
    thread_ts: str = "ts-1",
    user: str = "U1",
    project_id: str | None = "proj-abc",
    interactive: bool = False,
):
    """Helper to call kick_off_prd_flow with common patches."""
    from crewai_productfeature_planner.apis.slack._flow_handlers import (
        kick_off_prd_flow,
    )

    kick_off_prd_flow(
        channel=channel,
        thread_ts=thread_ts,
        user=user,
        idea=idea,
        event_ts="evt-1",
        interactive=interactive,
        project_id=project_id,
    )


class TestKickOffDedup:
    """kick_off_prd_flow must block duplicate ideas."""

    @patch(f"{_MODULE}.threading")
    @patch(_SLACK_CLIENT, return_value=None)
    @patch(
        f"{_WI_MODULE}.find_recent_duplicate_idea",
        return_value=None,
    )
    @patch(
        f"{_WI_MODULE}.find_active_duplicate_idea",
        return_value={"run_id": "active-run", "status": "inprogress"},
    )
    def test_blocks_active_duplicate(
        self, mock_active, mock_recent, mock_client, mock_threading,
    ):
        """Should NOT start a thread when an active duplicate exists."""
        _call_kickoff()

        mock_threading.Thread.assert_not_called()

    @patch(f"{_MODULE}.threading")
    @patch(_SLACK_CLIENT, return_value=None)
    @patch(
        f"{_WI_MODULE}.find_recent_duplicate_idea",
        return_value={"run_id": "done-run", "status": "completed"},
    )
    @patch(
        f"{_WI_MODULE}.find_active_duplicate_idea",
        return_value=None,
    )
    def test_blocks_recently_completed_duplicate(
        self, mock_active, mock_recent, mock_client, mock_threading,
    ):
        """Should NOT start a thread when a recently completed duplicate exists."""
        _call_kickoff()

        mock_threading.Thread.assert_not_called()

    @patch(f"{_MODULE}.threading")
    @patch(_SLACK_CLIENT, return_value=None)
    @patch(
        f"{_WI_MODULE}.find_recent_duplicate_idea",
        return_value=None,
    )
    @patch(
        f"{_WI_MODULE}.find_active_duplicate_idea",
        return_value=None,
    )
    def test_allows_unique_idea(
        self, mock_active, mock_recent, mock_client, mock_threading,
    ):
        """Should start a thread when no duplicate exists."""
        mock_thread = MagicMock()
        mock_threading.Thread.return_value = mock_thread
        mock_threading.Event.return_value = MagicMock()

        _call_kickoff()

        mock_threading.Thread.assert_called_once()
        mock_thread.start.assert_called_once()

    @patch(f"{_MODULE}.threading")
    @patch(_SLACK_CLIENT, return_value=None)
    @patch(
        f"{_WI_MODULE}.find_recent_duplicate_idea",
        return_value=None,
    )
    @patch(
        f"{_WI_MODULE}.find_active_duplicate_idea",
        return_value={"run_id": "active-run", "status": "paused"},
    )
    def test_blocks_paused_duplicate(
        self, mock_active, mock_recent, mock_client, mock_threading,
    ):
        """Should block when a paused flow with same idea exists."""
        _call_kickoff()

        mock_threading.Thread.assert_not_called()

    @patch(f"{_MODULE}.threading")
    @patch(_SLACK_CLIENT, return_value=None)
    @patch(
        f"{_WI_MODULE}.find_recent_duplicate_idea",
        return_value=None,
    )
    @patch(
        f"{_WI_MODULE}.find_active_duplicate_idea",
        return_value=None,
    )
    def test_dedup_uses_channel_when_no_project(
        self, mock_active, mock_recent, mock_client, mock_threading,
    ):
        """Should pass channel to duplicate checks when project_id is empty."""
        mock_thread = MagicMock()
        mock_threading.Thread.return_value = mock_thread
        mock_threading.Event.return_value = MagicMock()

        _call_kickoff(project_id=None)

        # Verify channel was passed to the duplicate check
        call_kwargs = mock_active.call_args
        assert call_kwargs[1]["channel"] == "C123"

    @patch(f"{_MODULE}.threading")
    @patch(_SLACK_CLIENT, return_value=None)
    @patch(
        f"{_WI_MODULE}.find_active_duplicate_idea",
        side_effect=Exception("DB down"),
    )
    def test_proceeds_on_dedup_error(
        self, mock_active, mock_client, mock_threading,
    ):
        """Should proceed with flow when duplicate check fails."""
        mock_thread = MagicMock()
        mock_threading.Thread.return_value = mock_thread
        mock_threading.Event.return_value = MagicMock()

        _call_kickoff()

        # Should still start the thread
        mock_threading.Thread.assert_called_once()
        mock_thread.start.assert_called_once()

    @patch(f"{_MODULE}.threading")
    @patch(_SLACK_CLIENT, return_value=None)
    @patch(
        f"{_WI_MODULE}.find_recent_duplicate_idea",
        return_value=None,
    )
    @patch(
        f"{_WI_MODULE}.find_active_duplicate_idea",
        return_value={"run_id": "active-run", "status": "inprogress"},
    )
    def test_blocks_interactive_mode_too(
        self, mock_active, mock_recent, mock_client, mock_threading,
    ):
        """Dedup should block regardless of interactive vs automated."""
        _call_kickoff(interactive=True)

        mock_threading.Thread.assert_not_called()
