"""Tests for admin gate on configure_memory in _next_step_handler."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

_HANDLER_MODULE = (
    "crewai_productfeature_planner.apis.slack.interactions_router._next_step_handler"
)
_SESSION_MODULE = (
    "crewai_productfeature_planner.apis.slack.session_manager"
)


_TOOLS_MODULE = "crewai_productfeature_planner.tools.slack_tools"


@pytest.fixture(autouse=True)
def _mock_slack_client():
    mock_client = MagicMock()
    with patch(f"{_TOOLS_MODULE}._get_slack_client", return_value=mock_client):
        yield mock_client


@pytest.fixture(autouse=True)
def _mock_record_feedback():
    with patch(
        "crewai_productfeature_planner.mongodb.agent_interactions.repository"
        ".record_next_step_feedback"
    ):
        yield


class TestConfigureMemoryAdminGate:
    """Non-admin users must be denied configure_memory via next-step accept."""

    def test_non_admin_blocked(self, _mock_slack_client):
        """Non-admin accepting configure_memory gets a denial."""
        from crewai_productfeature_planner.apis.slack.interactions_router._next_step_handler import (
            _handle_next_step_feedback,
        )

        with (
            patch(
                f"{_SESSION_MODULE}.get_context_session",
                return_value={"project_id": "p1", "project_name": "Test"},
            ),
            patch(f"{_SESSION_MODULE}.can_manage_memory", return_value=False),
        ):
            _handle_next_step_feedback(
                "next_step_accept", "configure_memory|int123",
                "U_NON_ADMIN", "C_CHAN", "T1",
            )

        posted = _mock_slack_client.chat_postMessage.call_args
        assert ":lock:" in posted.kwargs.get("text", posted[1].get("text", ""))

    def test_admin_allowed(self, _mock_slack_client):
        """Admin accepting configure_memory proceeds to handler."""
        from crewai_productfeature_planner.apis.slack.interactions_router._next_step_handler import (
            _handle_next_step_feedback,
        )

        with (
            patch(
                f"{_SESSION_MODULE}.get_context_session",
                return_value={"project_id": "p1", "project_name": "Test"},
            ),
            patch(f"{_SESSION_MODULE}.can_manage_memory", return_value=True),
            patch(
                "crewai_productfeature_planner.apis.slack._session_handlers"
                ".handle_configure_memory",
            ) as mock_handler,
        ):
            _handle_next_step_feedback(
                "next_step_accept", "configure_memory|int123",
                "U_ADMIN", "C_CHAN", "T1",
            )

        mock_handler.assert_called_once()
