"""Tests for active-flow guard — blocks config changes during in-progress flows.

Feature 1: Admin guardrails prevent project configuration during active
idea flows.  Config is allowed before an idea starts or after it completes
(ready to publish to Confluence).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.apis.slack.interactions_router._command_handler import (
    _CONFIG_ACTIONS,
    _handle_command_action,
)

_MOD = "crewai_productfeature_planner.apis.slack.interactions_router._command_handler"
_SESSION_MOD = "crewai_productfeature_planner.apis.slack.session_manager"
_ER = "crewai_productfeature_planner.apis.slack.events_router"
_MSG = "crewai_productfeature_planner.apis.slack._message_handler"
_TOOLS_MODULE = "crewai_productfeature_planner.tools.slack_tools"


# ---------------------------------------------------------------------------
# Helper: shortcut to invoke _interpret_and_act with mocked LLM
# ---------------------------------------------------------------------------

def _call_interpret_and_act(
    intent: str,
    text: str = "configure project",
    session_project_id: str | None = "proj-1",
    flow_active: bool = False,
    is_admin: bool = True,
):
    """Call _interpret_and_act with stubbed dependencies."""
    interpretation = json.dumps({
        "intent": intent,
        "idea": None,
        "reply": "",
    })
    mock_interpret = MagicMock()
    mock_interpret.run.return_value = interpretation
    mock_send = MagicMock()
    mock_client = MagicMock()

    session = {"project_id": session_project_id} if session_project_id else None

    patches = [
        patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool", return_value=mock_interpret),
        patch(f"{_TOOLS_MODULE}.SlackSendMessageTool", return_value=mock_send),
        patch(f"{_SESSION_MOD}.get_context_session", return_value=session),
        patch(f"{_SESSION_MOD}.can_manage_memory", return_value=is_admin),
        patch(
            f"{_TOOLS_MODULE}._get_slack_client",
            return_value=mock_client,
        ),
        patch(
            "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction",
            MagicMock(),
        ),
        patch(f"{_MSG}._is_flow_active", return_value=flow_active),
    ]

    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        from crewai_productfeature_planner.apis.slack import events_router as er
        er._interpret_and_act("C1", "T1", "U1", text, "E1")

    return mock_send, mock_client


# ---------------------------------------------------------------------------
# Command handler: config actions blocked by active-flow guard
# ---------------------------------------------------------------------------


class TestCommandHandlerActiveFlowGuard:
    """cmd_configure_project and cmd_configure_memory should be blocked
    when an idea flow is in-progress for the active project."""

    @pytest.fixture(autouse=True)
    def _stub_session(self):
        with (
            patch(f"{_SESSION_MOD}.get_context_session",
                  return_value={"project_id": "proj-1"}),
            patch(f"{_SESSION_MOD}.can_manage_memory", return_value=True),
        ):
            yield

    @pytest.mark.parametrize("action_id", sorted(_CONFIG_ACTIONS))
    def test_config_blocked_when_flow_active(self, action_id):
        """Config actions should call _deny_active_flow when flow is active."""
        with (
            patch(f"{_MOD}._is_flow_active", return_value=True),
            patch(f"{_MOD}._deny_active_flow") as mock_deny,
        ):
            _handle_command_action(action_id, "U1", "C1", "T1")
            mock_deny.assert_called_once_with("C1", "T1", "U1")

    @pytest.mark.parametrize("action_id", sorted(_CONFIG_ACTIONS))
    def test_config_allowed_when_no_active_flow(self, action_id):
        """Config actions should proceed normally when no flow is active."""
        handler_map = {
            "cmd_configure_project": "crewai_productfeature_planner.apis.slack._session_handlers.handle_update_config",
            "cmd_configure_memory": "crewai_productfeature_planner.apis.slack._session_handlers.handle_configure_memory",
        }
        with (
            patch(f"{_MOD}._is_flow_active", return_value=False),
            patch(f"{_MOD}._deny_active_flow") as mock_deny,
            patch(handler_map[action_id]),
        ):
            _handle_command_action(action_id, "U1", "C1", "T1")
            mock_deny.assert_not_called()

    def test_config_allowed_when_no_project_session(self):
        """Config should not be blocked when there's no project session."""
        with (
            patch(f"{_SESSION_MOD}.get_context_session", return_value=None),
            patch(f"{_MOD}._is_flow_active") as mock_check,
            patch(f"{_MOD}._deny_active_flow") as mock_deny,
            patch("crewai_productfeature_planner.apis.slack._session_handlers.handle_update_config"),
        ):
            _handle_command_action("cmd_configure_project", "U1", "C1", "T1")
            mock_check.assert_not_called()
            mock_deny.assert_not_called()

    def test_non_config_actions_not_blocked(self):
        """Non-config actions like cmd_list_ideas should not be affected."""
        with (
            patch(f"{_MOD}._is_flow_active", return_value=True),
            patch(f"{_MOD}._deny_active_flow") as mock_deny,
            patch("crewai_productfeature_planner.apis.slack._session_handlers.handle_list_ideas"),
        ):
            _handle_command_action("cmd_list_ideas", "U1", "C1", "T1")
            mock_deny.assert_not_called()


# ---------------------------------------------------------------------------
# Message handler: update_config and configure_memory blocked by guard
# ---------------------------------------------------------------------------


class TestMessageHandlerActiveFlowGuard:
    """update_config and configure_memory intents should be blocked
    when an idea flow is in-progress for the active project."""

    def test_update_config_blocked_when_flow_active(self):
        """update_config intent should post warning when flow is active."""
        mock_send, mock_client = _call_interpret_and_act(
            intent="update_config",
            text="configure project",
            flow_active=True,
        )
        # Should have posted a warning message (via client.chat_postMessage
        # or send_tool.run)
        all_calls = mock_send.run.call_args_list + mock_client.chat_postMessage.call_args_list
        any_warning = any(
            "active" in str(c).lower() or "in progress" in str(c).lower()
            for c in all_calls
        )
        assert any_warning, (
            "Expected a warning about active flow, but got: "
            f"{[str(c) for c in all_calls]}"
        )

    def test_update_config_allowed_when_no_flow(self):
        """update_config intent should dispatch normally when no flow active."""
        interpretation = json.dumps({
            "intent": "update_config",
            "idea": None,
            "reply": "",
        })
        mock_interpret = MagicMock()
        mock_interpret.run.return_value = interpretation
        mock_send = MagicMock()
        mock_client = MagicMock()

        session = {"project_id": "proj-1"}

        with (
            patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool", return_value=mock_interpret),
            patch(f"{_TOOLS_MODULE}.SlackSendMessageTool", return_value=mock_send),
            patch(f"{_SESSION_MOD}.get_context_session", return_value=session),
            patch(f"{_SESSION_MOD}.can_manage_memory", return_value=True),
            patch(f"{_TOOLS_MODULE}._get_slack_client", return_value=mock_client),
            patch(
                "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction",
                MagicMock(),
            ),
            patch(f"{_MSG}._is_flow_active", return_value=False),
            patch(f"{_ER}._handle_update_config") as mock_handler,
        ):
            from crewai_productfeature_planner.apis.slack import events_router as er
            er._interpret_and_act("C1", "T1", "U1", "configure project", "E1")
            mock_handler.assert_called_once()

    def test_configure_memory_blocked_when_flow_active(self):
        """configure_memory intent should post warning when flow is active."""
        mock_send, mock_client = _call_interpret_and_act(
            intent="configure_memory",
            text="configure memory",
            flow_active=True,
        )
        all_calls = mock_send.run.call_args_list + mock_client.chat_postMessage.call_args_list
        any_warning = any(
            "active" in str(c).lower() or "in progress" in str(c).lower()
            for c in all_calls
        )
        assert any_warning

    def test_configure_memory_allowed_when_no_flow(self):
        """configure_memory intent should dispatch normally when no flow active."""
        interpretation = json.dumps({
            "intent": "configure_memory",
            "idea": None,
            "reply": "",
        })
        mock_interpret = MagicMock()
        mock_interpret.run.return_value = interpretation
        mock_send = MagicMock()
        mock_client = MagicMock()

        session = {"project_id": "proj-1"}

        with (
            patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool", return_value=mock_interpret),
            patch(f"{_TOOLS_MODULE}.SlackSendMessageTool", return_value=mock_send),
            patch(f"{_SESSION_MOD}.get_context_session", return_value=session),
            patch(f"{_SESSION_MOD}.can_manage_memory", return_value=True),
            patch(f"{_TOOLS_MODULE}._get_slack_client", return_value=mock_client),
            patch(
                "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction",
                MagicMock(),
            ),
            patch(f"{_MSG}._is_flow_active", return_value=False),
            patch(f"{_ER}._handle_configure_memory") as mock_handler,
        ):
            from crewai_productfeature_planner.apis.slack import events_router as er
            er._interpret_and_act("C1", "T1", "U1", "configure memory", "E1")
            mock_handler.assert_called_once()


# ---------------------------------------------------------------------------
# MongoDB utility: has_active_idea_flow
# ---------------------------------------------------------------------------


class TestHasActiveIdeaFlow:
    """Tests for the MongoDB query utility."""

    def test_returns_true_when_inprogress_idea_exists(self):
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_db)
        mock_db.count_documents.return_value = 1

        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas._queries._common.get_db",
            return_value=mock_db,
        ):
            from crewai_productfeature_planner.mongodb.working_ideas._queries import (
                has_active_idea_flow,
            )
            assert has_active_idea_flow("proj-1") is True

        mock_db.count_documents.assert_called_once_with(
            {"project_id": "proj-1", "status": "inprogress"},
            limit=1,
        )

    def test_returns_false_when_no_inprogress_ideas(self):
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_db)
        mock_db.count_documents.return_value = 0

        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas._queries._common.get_db",
            return_value=mock_db,
        ):
            from crewai_productfeature_planner.mongodb.working_ideas._queries import (
                has_active_idea_flow,
            )
            assert has_active_idea_flow("proj-1") is False

    def test_returns_false_on_error(self):
        from pymongo.errors import PyMongoError

        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas._queries._common.get_db",
            side_effect=PyMongoError("connection lost"),
        ):
            from crewai_productfeature_planner.mongodb.working_ideas._queries import (
                has_active_idea_flow,
            )
            assert has_active_idea_flow("proj-1") is False
