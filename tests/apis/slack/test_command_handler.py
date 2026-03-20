"""Tests for _command_handler.py — cmd_* button dispatch."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.apis.slack.interactions_router._command_handler import (
    CMD_ACTIONS,
    _handle_command_action,
)

_MOD = "crewai_productfeature_planner.apis.slack.interactions_router._command_handler"
_SESSION_MOD = "crewai_productfeature_planner.apis.slack.session_manager"


@pytest.fixture(autouse=True)
def _stub_session():
    """Stub get_context_session so no MongoDB is needed."""
    with patch(f"{_SESSION_MOD}.get_context_session", return_value=None):
        yield


class TestCMDActions:
    def test_all_start_with_cmd(self):
        for action in CMD_ACTIONS:
            assert action.startswith("cmd_")

    def test_expected_count(self):
        assert len(CMD_ACTIONS) == 11


# ---------------------------------------------------------------------------
# Dispatch routing
# ---------------------------------------------------------------------------


class TestDispatchRouting:
    """Each cmd_* action should invoke the correct handler."""

    def test_list_ideas(self):
        with patch(
            "crewai_productfeature_planner.apis.slack._session_handlers.handle_list_ideas"
        ) as mock:
            _handle_command_action("cmd_list_ideas", "U1", "C1", "T1")
            mock.assert_called_once_with("C1", "T1", "U1", None)

    def test_list_products(self):
        with patch(
            "crewai_productfeature_planner.apis.slack._session_handlers.handle_list_products"
        ) as mock:
            _handle_command_action("cmd_list_products", "U1", "C1", "T1")
            mock.assert_called_once_with("C1", "T1", "U1", None)

    def test_configure_project(self):
        with patch(
            "crewai_productfeature_planner.apis.slack._session_handlers.handle_update_config"
        ) as mock:
            _handle_command_action("cmd_configure_project", "U1", "C1", "T1")
            mock.assert_called_once_with("C1", "T1", "U1", None)

    def test_configure_memory(self):
        with patch(
            "crewai_productfeature_planner.apis.slack._session_handlers.handle_configure_memory"
        ) as mock:
            _handle_command_action("cmd_configure_memory", "U1", "C1", "T1")
            mock.assert_called_once_with("C1", "T1", "U1", None)

    def test_switch_project(self):
        with patch(
            "crewai_productfeature_planner.apis.slack._session_handlers.handle_switch_project"
        ) as mock:
            _handle_command_action("cmd_switch_project", "U1", "C1", "T1")
            mock.assert_called_once_with("C1", "T1", "U1")

    def test_end_session(self):
        with patch(
            "crewai_productfeature_planner.apis.slack._session_handlers.handle_end_session"
        ) as mock:
            _handle_command_action("cmd_end_session", "U1", "C1", "T1")
            mock.assert_called_once_with("C1", "T1", "U1")

    def test_resume_prd(self):
        with patch(
            "crewai_productfeature_planner.apis.slack._flow_handlers.handle_resume_prd"
        ) as mock:
            _handle_command_action("cmd_resume_prd", "U1", "C1", "T1")
            mock.assert_called_once()
            call_args = mock.call_args
            assert call_args[0][:3] == ("C1", "T1", "U1")

    def test_create_project(self):
        with patch(
            "crewai_productfeature_planner.apis.slack._session_handlers.handle_create_project_intent"
        ) as mock:
            _handle_command_action("cmd_create_project", "U1", "C1", "T1")
            mock.assert_called_once_with("C1", "T1", "U1")

    def test_list_projects(self):
        with patch(
            "crewai_productfeature_planner.apis.slack._session_handlers.prompt_project_selection"
        ) as mock:
            _handle_command_action("cmd_list_projects", "U1", "C1", "T1")
            mock.assert_called_once_with("C1", "T1", "U1")

    def test_help(self):
        with patch(f"{_MOD}._handle_help") as mock:
            _handle_command_action("cmd_help", "U1", "C1", "T1")
            mock.assert_called_once_with("C1", "T1", "U1", None)

    def test_check_publish(self):
        with patch(
            "crewai_productfeature_planner.apis.slack._flow_handlers.handle_check_publish_intent"
        ) as mock:
            _handle_command_action("cmd_check_publish", "U1", "C1", "T1")
            mock.assert_called_once()

    def test_unknown_action_logs_warning(self):
        """Unknown cmd_ action should not raise — just log."""
        _handle_command_action("cmd_nonexistent", "U1", "C1", "T1")


# ---------------------------------------------------------------------------
# Help handler
# ---------------------------------------------------------------------------


class TestHandleHelp:
    def test_posts_blocks_when_client_available(self):
        mock_client = MagicMock()
        with (
            patch(
                "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
                return_value=mock_client,
            ),
            patch(f"{_SESSION_MOD}.get_context_session", return_value=None),
        ):
            _handle_command_action("cmd_help", "U1", "C1", "T1")
        mock_client.chat_postMessage.assert_called_once()
        call_kwargs = mock_client.chat_postMessage.call_args[1]
        assert "blocks" in call_kwargs
        assert call_kwargs["channel"] == "C1"

    def test_no_client_no_error(self):
        """When no Slack client available, should not raise."""
        with (
            patch(
                "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
                return_value=None,
            ),
            patch(f"{_SESSION_MOD}.get_context_session", return_value=None),
        ):
            _handle_command_action("cmd_help", "U1", "C1", "T1")
