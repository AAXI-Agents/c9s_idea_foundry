"""Tests for _command_handler.py — cmd_* button dispatch."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.apis.slack.interactions_router._command_handler import (
    _ADMIN_ACTIONS,
    CMD_ACTIONS,
    _handle_command_action,
)

_MOD = "crewai_productfeature_planner.apis.slack.interactions_router._command_handler"
_SESSION_MOD = "crewai_productfeature_planner.apis.slack.session_manager"


@pytest.fixture(autouse=True)
def _stub_session():
    """Stub get_context_session and can_manage_memory so no MongoDB/Slack API is needed."""
    with (
        patch(f"{_SESSION_MOD}.get_context_session", return_value=None),
        patch(f"{_SESSION_MOD}.can_manage_memory", return_value=True),
    ):
        yield


class TestCMDActions:
    def test_all_start_with_cmd(self):
        for action in CMD_ACTIONS:
            assert action.startswith("cmd_")

    def test_expected_count(self):
        assert len(CMD_ACTIONS) == 15


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

    def test_unknown_action_logs_warning(self):
        """Unknown cmd_ action should not raise — just log."""
        _handle_command_action("cmd_nonexistent", "U1", "C1", "T1")

    def test_restart_prd(self):
        with patch(
            "crewai_productfeature_planner.apis.slack._flow_handlers.handle_restart_prd"
        ) as mock:
            _handle_command_action("cmd_restart_prd", "U1", "C1", "T1")
            mock.assert_called_once()
            assert mock.call_args[0][:3] == ("C1", "T1", "U1")

    def test_current_project(self):
        with patch(
            "crewai_productfeature_planner.apis.slack._session_project.handle_current_project"
        ) as mock:
            _handle_command_action("cmd_current_project", "U1", "C1", "T1")
            mock.assert_called_once_with("C1", "T1", "U1", None)

    def test_create_prd(self):
        with patch(
            "crewai_productfeature_planner.apis.slack._session_reply.reply"
        ) as mock:
            _handle_command_action("cmd_create_prd", "U1", "C1", "T1")
            mock.assert_called_once()
            assert "idea" in mock.call_args[0][2].lower()

    def test_iterate_idea(self):
        with patch(
            "crewai_productfeature_planner.apis.slack._session_ideas.handle_iterate_idea"
        ) as mock:
            _handle_command_action("cmd_iterate_idea", "U1", "C1", "T1")
            mock.assert_called_once_with("C1", "T1", "U1", None)


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


# ---------------------------------------------------------------------------
# Admin gate
# ---------------------------------------------------------------------------


class TestAdminGate:
    """Admin-only actions should be blocked for non-admin users in channels."""

    @pytest.mark.parametrize("action_id", sorted(_ADMIN_ACTIONS))
    def test_admin_action_blocked_for_non_admin(self, action_id):
        """Non-admin users get a denial message instead of the handler."""
        with (
            patch(f"{_SESSION_MOD}.get_context_session", return_value=None),
            patch(f"{_SESSION_MOD}.can_manage_memory", return_value=False),
            patch(f"{_MOD}._deny_non_admin") as mock_deny,
        ):
            _handle_command_action(action_id, "U1", "C1", "T1")
            mock_deny.assert_called_once_with("C1", "T1", "U1")

    @pytest.mark.parametrize("action_id", sorted(_ADMIN_ACTIONS))
    def test_admin_action_allowed_for_admin(self, action_id):
        """Admin users can use admin-only actions without denial."""
        with (
            patch(f"{_SESSION_MOD}.get_context_session", return_value=None),
            patch(f"{_SESSION_MOD}.can_manage_memory", return_value=True),
            patch(f"{_MOD}._deny_non_admin") as mock_deny,
        ):
            handler_map = {
                "cmd_configure_project": "crewai_productfeature_planner.apis.slack._session_handlers.handle_update_config",
                "cmd_configure_memory": "crewai_productfeature_planner.apis.slack._session_handlers.handle_configure_memory",
                "cmd_switch_project": "crewai_productfeature_planner.apis.slack._session_handlers.handle_switch_project",
                "cmd_create_project": "crewai_productfeature_planner.apis.slack._session_handlers.handle_create_project_intent",
            }
            with patch(handler_map[action_id]):
                _handle_command_action(action_id, "U1", "C1", "T1")
            mock_deny.assert_not_called()

    @pytest.mark.parametrize("action_id", [
        "cmd_list_ideas", "cmd_list_products", "cmd_resume_prd",
        "cmd_help",
    ])
    def test_non_admin_actions_always_allowed(self, action_id):
        """Non-admin-gated actions should work for any user."""
        with (
            patch(f"{_SESSION_MOD}.get_context_session", return_value=None),
            patch(f"{_SESSION_MOD}.can_manage_memory", return_value=False),
            patch(f"{_MOD}._deny_non_admin") as mock_deny,
        ):
            patches = [
                patch("crewai_productfeature_planner.apis.slack._session_handlers.handle_list_ideas"),
                patch("crewai_productfeature_planner.apis.slack._session_handlers.handle_list_products"),
                patch("crewai_productfeature_planner.apis.slack._flow_handlers.handle_resume_prd"),
                patch("crewai_productfeature_planner.tools.slack_tools._get_slack_client", return_value=None),
            ]
            for p in patches:
                p.start()
            try:
                _handle_command_action(action_id, "U1", "C1", "T1")
            finally:
                for p in patches:
                    p.stop()
            mock_deny.assert_not_called()
