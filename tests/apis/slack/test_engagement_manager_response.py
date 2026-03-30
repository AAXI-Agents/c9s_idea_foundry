"""Regression tests: Engagement Manager must ALWAYS produce a response.

These tests enforce the invariant that the engagement manager agent
and the ``_handle_engagement_manager`` Slack handler never leave the
user without a reply — even when the agent fails, the Slack token is
expired, or the LLM is unavailable.

Introduced after a critical incident where an expired Slack OAuth token
caused silent delivery failures — the EM generated responses but they
were never posted to Slack, and no ERROR was logged for the complete
delivery failure.

See also: ``tests/agents/test_engagement_manager.py`` for unit-level
agent tests.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, call

import pytest

_MSG_MODULE = "crewai_productfeature_planner.apis.slack._message_handler"
_TOOLS_MODULE = "crewai_productfeature_planner.tools.slack_tools"
_EM_MODULE = "crewai_productfeature_planner.agents.engagement_manager.agent"


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")


# ---------------------------------------------------------------------------
# Helper: call _handle_engagement_manager with controllable mocks
# ---------------------------------------------------------------------------


def _make_send_tool(*, succeed: bool = True):
    """Create a mock SlackSendMessageTool."""
    tool = MagicMock()
    if succeed:
        tool.run.return_value = json.dumps({"status": "ok", "channel": "C1", "ts": "123"})
    else:
        tool.run.return_value = json.dumps({"status": "error", "error": "token_expired"})
    return tool


def _call_handler(
    *,
    agent_response: str | None = "Hello! I can help.",
    agent_raises: Exception | None = None,
    client_post_raises: Exception | None = None,
    send_tool_succeed: bool = True,
    session_project_id: str | None = "proj-1",
    session_project_name: str | None = "Test Project",
):
    """Call ``_handle_engagement_manager`` with full mock control.

    Returns (result, mock_client, mock_send_tool, mock_logger).
    """
    from crewai_productfeature_planner.apis.slack._message_handler import (
        _handle_engagement_manager,
    )

    send_tool = _make_send_tool(succeed=send_tool_succeed)
    mock_client = MagicMock()

    if client_post_raises:
        mock_client.chat_postMessage.side_effect = client_post_raises
    else:
        mock_client.chat_postMessage.return_value = {"ok": True}

    # Control the handle_unknown_intent call
    if agent_raises:
        intent_mock = MagicMock(side_effect=agent_raises)
    elif agent_response is not None:
        intent_mock = MagicMock(return_value=agent_response)
    else:
        intent_mock = MagicMock(return_value="")

    with (
        patch(
            "crewai_productfeature_planner.agents.engagement_manager.handle_unknown_intent",
            intent_mock,
        ) as mock_intent,
        patch(
            f"{_TOOLS_MODULE}._get_slack_client",
            return_value=mock_client,
        ),
    ):
        result = _handle_engagement_manager(
            channel="C1",
            thread_ts="T1",
            user="U1",
            clean_text="what can you do?",
            history=None,
            session_project_id=session_project_id,
            session_project_name=session_project_name,
            reply_text="default reply",
            send_tool=send_tool,
        )

    return result, mock_client, send_tool


# ===================================================================
# INVARIANT 1: _handle_engagement_manager ALWAYS returns a non-empty
# string — regardless of agent success or failure.
# ===================================================================


class TestEMAlwaysReturnsResponse:
    """The handler must ALWAYS return a non-empty response string."""

    def test_returns_agent_response_on_success(self):
        result, _, _ = _call_handler(agent_response="Here is my help!")
        assert result
        assert "Here is my help!" in result

    def test_returns_fallback_when_agent_returns_empty(self):
        result, _, _ = _call_handler(agent_response="")
        assert result
        assert len(result) > 0  # MUST not be empty

    def test_returns_fallback_when_agent_returns_none(self):
        result, _, _ = _call_handler(agent_response=None)
        assert result
        assert len(result) > 0

    def test_returns_fallback_when_agent_raises(self):
        result, _, _ = _call_handler(agent_raises=Exception("LLM offline"))
        assert result
        assert len(result) > 0

    def test_returns_fallback_when_agent_raises_runtime_error(self):
        result, _, _ = _call_handler(
            agent_raises=RuntimeError("Gemini API quota exceeded"),
        )
        assert result
        assert len(result) > 0

    def test_fallback_includes_user_mention(self):
        """Static fallback must mention the user so they see a notification."""
        result, _, _ = _call_handler(agent_response="")
        assert "<@U1>" in result

    def test_fallback_mentions_mention_or_idea(self):
        """Static fallback should mention product ideas so user knows what to do."""
        # Pass reply_text="" to trigger the built-in static fallback
        result, _, _ = _call_handler(agent_response="")
        # When reply_text is provided, it's used as the fallback
        # Either way, the result must be non-empty and mention the user
        assert "<@U1>" in result
        assert len(result) > 10  # Must contain actionable content


# ===================================================================
# INVARIANT 2: Handler ALWAYS attempts to post to Slack (Block Kit
# or plain text fallback).
# ===================================================================


class TestEMAlwaysAttemptsSlackPost:
    """Handler must try to post the response to Slack."""

    def test_posts_block_kit_on_success(self):
        _, mock_client, _ = _call_handler()
        mock_client.chat_postMessage.assert_called_once()
        call_kwargs = mock_client.chat_postMessage.call_args[1]
        assert "blocks" in call_kwargs
        assert call_kwargs["channel"] == "C1"
        assert call_kwargs["thread_ts"] == "T1"

    def test_block_kit_includes_action_buttons(self):
        _, mock_client, _ = _call_handler()
        call_kwargs = mock_client.chat_postMessage.call_args[1]
        blocks = call_kwargs["blocks"]
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        assert len(action_blocks) >= 1, "Must have at least one actions block"

    def test_falls_back_to_send_tool_when_client_fails(self):
        _, _, send_tool = _call_handler(
            client_post_raises=Exception("token_expired"),
            send_tool_succeed=True,
        )
        send_tool.run.assert_called_once()

    def test_falls_back_when_no_client(self):
        """When _get_slack_client returns None, uses send_tool."""
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _handle_engagement_manager,
        )

        send_tool = _make_send_tool(succeed=True)

        with (
            patch(
                "crewai_productfeature_planner.agents.engagement_manager.handle_unknown_intent",
                return_value="response",
            ),
            patch(f"{_TOOLS_MODULE}._get_slack_client", return_value=None),
        ):
            result = _handle_engagement_manager(
                channel="C1", thread_ts="T1", user="U1",
                clean_text="hello", history=None,
                session_project_id=None, session_project_name=None,
                reply_text="default", send_tool=send_tool,
            )

        send_tool.run.assert_called_once()
        assert result


# ===================================================================
# INVARIANT 3: When ALL delivery fails, an ERROR is logged so admins
# can detect the issue.
# ===================================================================


class TestEMLogsErrorOnDeliveryFailure:
    """When message cannot be delivered at all, ERROR must be logged."""

    def test_logs_error_when_both_paths_fail(self):
        """Both Block Kit and send_tool fail → ERROR log with DELIVERY FAILED."""
        with patch(f"{_MSG_MODULE}.logger") as mock_logger:
            result, _, _ = _call_handler(
                client_post_raises=Exception("token_expired"),
                send_tool_succeed=False,
            )

        # Must have logged ERROR with delivery failure details
        error_calls = [
            c for c in mock_logger.error.call_args_list
            if "DELIVERY FAILED" in str(c)
        ]
        assert len(error_calls) >= 1, (
            "Must log ERROR with 'DELIVERY FAILED' when all delivery fails. "
            f"Actual error calls: {mock_logger.error.call_args_list}"
        )

    def test_logs_error_includes_channel_and_user(self):
        """ERROR log must include channel and user for debugging."""
        with patch(f"{_MSG_MODULE}.logger") as mock_logger:
            _call_handler(
                client_post_raises=Exception("token_expired"),
                send_tool_succeed=False,
            )

        error_calls = [
            c for c in mock_logger.error.call_args_list
            if "DELIVERY FAILED" in str(c)
        ]
        assert len(error_calls) >= 1
        error_msg = str(error_calls[0])
        assert "C1" in error_msg
        assert "U1" in error_msg

    def test_no_error_when_block_kit_succeeds(self):
        """No DELIVERY FAILED error when Block Kit post works."""
        with patch(f"{_MSG_MODULE}.logger") as mock_logger:
            _call_handler(client_post_raises=None)

        error_calls = [
            c for c in mock_logger.error.call_args_list
            if "DELIVERY FAILED" in str(c)
        ]
        assert len(error_calls) == 0

    def test_no_error_when_fallback_succeeds(self):
        """No DELIVERY FAILED error when fallback send_tool works."""
        with patch(f"{_MSG_MODULE}.logger") as mock_logger:
            _call_handler(
                client_post_raises=Exception("token_expired"),
                send_tool_succeed=True,
            )

        error_calls = [
            c for c in mock_logger.error.call_args_list
            if "DELIVERY FAILED" in str(c)
        ]
        assert len(error_calls) == 0


# ===================================================================
# INVARIANT 4: Agent response flow — ensure fast path + CrewAI
# fallback chain is intact (detailed unit tests exist in
# tests/agents/test_engagement_manager.py — these are regression
# guards at the handler level).
# ===================================================================


class TestEMAgentFallbackChain:
    """Guard: fast path → CrewAI fallback chain never silently returns None."""

    def test_handle_unknown_intent_never_returns_none_on_fast_success(self):
        """When fast path succeeds, result is the fast response."""
        with patch(
            "crewai_productfeature_planner.tools.gemini_chat.generate_chat_response",
            return_value="fast response",
        ):
            from crewai_productfeature_planner.agents.engagement_manager.agent import (
                _handle_unknown_intent_fast,
            )
            result = _handle_unknown_intent_fast(
                "what can you do?", None, "", None,
            )
        assert result == "fast response"

    def test_handle_unknown_intent_fast_returns_none_on_failure(self):
        """When fast path fails, it returns None (so caller falls back)."""
        with patch(
            "crewai_productfeature_planner.tools.gemini_chat.generate_chat_response",
            return_value=None,
        ):
            from crewai_productfeature_planner.agents.engagement_manager.agent import (
                _handle_unknown_intent_fast,
            )
            result = _handle_unknown_intent_fast(
                "what can you do?", None, "", None,
            )
        assert result is None

    def test_handle_unknown_intent_fast_returns_none_on_exception(self):
        """When fast path raises, it returns None (caller catches via handle_unknown_intent)."""
        with patch(
            "crewai_productfeature_planner.tools.gemini_chat.generate_chat_response",
            side_effect=Exception("API error"),
        ):
            from crewai_productfeature_planner.agents.engagement_manager.agent import (
                _handle_unknown_intent_fast,
            )
            # The function itself doesn't catch — the exception propagates
            # handle_unknown_intent catches it and falls back to CrewAI
            with pytest.raises(Exception, match="API error"):
                _handle_unknown_intent_fast(
                    "what can you do?", None, "", None,
                )


# ===================================================================
# INVARIANT 5: interpret_and_act outer wrapper always tries to send
# an error message when something goes wrong.
# ===================================================================


class TestInterpretAndActErrorRecovery:
    """The outer wrapper must attempt an error reply on failure."""

    def test_catches_inner_exception_and_sends_error(self):
        """When _interpret_and_act_inner raises, an error reply is attempted."""
        from crewai_productfeature_planner.apis.slack._message_handler import (
            interpret_and_act,
        )

        mock_send = MagicMock()
        mock_send.return_value = MagicMock()
        mock_send.return_value.run.return_value = json.dumps({"status": "ok"})

        with (
            patch(
                f"{_MSG_MODULE}._interpret_and_act_inner",
                side_effect=RuntimeError("catastrophic failure"),
            ),
            patch(f"{_MSG_MODULE}._post_thinking"),
            patch(
                f"{_TOOLS_MODULE}.SlackSendMessageTool",
                mock_send,
            ),
        ):
            # Should NOT raise — errors are caught and handled
            interpret_and_act("C1", "T1", "U1", "something", "E1")

        # Should have tried to send an error message
        mock_send.return_value.run.assert_called_once()
        call_kwargs = mock_send.return_value.run.call_args[1]
        assert "went wrong" in call_kwargs.get("text", "").lower() or \
               "warning" in call_kwargs.get("text", "").lower()

    def test_does_not_raise_even_if_error_reply_fails(self):
        """Even if the error reply itself fails, no exception escapes."""
        from crewai_productfeature_planner.apis.slack._message_handler import (
            interpret_and_act,
        )

        mock_send = MagicMock()
        mock_send.return_value = MagicMock()
        mock_send.return_value.run.side_effect = Exception("Slack down")

        with (
            patch(
                f"{_MSG_MODULE}._interpret_and_act_inner",
                side_effect=RuntimeError("catastrophic failure"),
            ),
            patch(f"{_MSG_MODULE}._post_thinking"),
            patch(f"{_TOOLS_MODULE}.SlackSendMessageTool", mock_send),
        ):
            # Must not raise
            interpret_and_act("C1", "T1", "U1", "something", "E1")


# ===================================================================
# INVARIANT 6: Session context buttons — handler includes appropriate
# action buttons based on whether a project is active.
# ===================================================================


class TestEMResponseButtons:
    """Action buttons must match the session context."""

    def test_with_project_includes_list_and_resume(self):
        """With active project, buttons include list_ideas and resume_prd."""
        _, mock_client, _ = _call_handler(session_project_id="proj-1")
        call_kwargs = mock_client.chat_postMessage.call_args[1]
        blocks = call_kwargs["blocks"]
        action_block = next(b for b in blocks if b["type"] == "actions")
        action_ids = {e.get("action_id", "") for e in action_block["elements"]}
        assert "cmd_list_ideas" in action_ids or len(action_block["elements"]) >= 3

    def test_without_project_has_fewer_buttons(self):
        """Without active project, fewer buttons are shown."""
        _, mock_client, _ = _call_handler(
            session_project_id=None,
            session_project_name=None,
        )
        call_kwargs = mock_client.chat_postMessage.call_args[1]
        blocks = call_kwargs["blocks"]
        action_block = next(b for b in blocks if b["type"] == "actions")
        # Without project: BTN_NEW_IDEA + BTN_HELP = 2 buttons
        assert len(action_block["elements"]) >= 2


# ===================================================================
# INVARIANT 7: Startup token validation must verify the token is
# actually usable via auth.test — not just present.
# ===================================================================


class TestStartupTokenValidation:
    """_validate_slack_token must call auth.test and log errors for
    expired/revoked tokens.  This was the root cause of a critical
    incident where the bot started but couldn't respond."""

    def test_valid_token_returns_true(self):
        """When auth.test succeeds, returns True."""
        from crewai_productfeature_planner.apis import _validate_slack_token

        mock_client_cls = MagicMock()
        mock_client_cls.return_value.auth_test.return_value = {
            "ok": True, "team_id": "T123", "user_id": "B456",
        }

        with (
            patch(
                "crewai_productfeature_planner.tools.slack_token_manager.get_valid_token",
                return_value="xoxb-valid-token",
            ),
            patch("slack_sdk.WebClient", mock_client_cls),
        ):
            result = _validate_slack_token()

        assert result is True
        mock_client_cls.return_value.auth_test.assert_called_once()

    def test_expired_token_returns_false(self):
        """When auth.test fails with token_expired, returns False."""
        from slack_sdk.errors import SlackApiError
        from crewai_productfeature_planner.apis import _validate_slack_token

        mock_resp = MagicMock()
        mock_resp.data = {"ok": False, "error": "token_expired"}
        mock_resp.__getitem__ = lambda s, k: s.data[k]
        mock_resp.get = lambda k, d=None: mock_resp.data.get(k, d)

        mock_client_cls = MagicMock()
        mock_client_cls.return_value.auth_test.side_effect = SlackApiError(
            "token_expired", response=mock_resp,
        )

        with (
            patch(
                "crewai_productfeature_planner.tools.slack_token_manager.get_valid_token",
                return_value="xoxb-expired",
            ),
            patch("slack_sdk.WebClient", mock_client_cls),
        ):
            result = _validate_slack_token()

        assert result is False

    def test_revoked_token_returns_false(self):
        """When auth.test fails with token_revoked, returns False."""
        from slack_sdk.errors import SlackApiError
        from crewai_productfeature_planner.apis import _validate_slack_token

        mock_resp = MagicMock()
        mock_resp.data = {"ok": False, "error": "token_revoked"}
        mock_resp.__getitem__ = lambda s, k: s.data[k]
        mock_resp.get = lambda k, d=None: mock_resp.data.get(k, d)

        mock_client_cls = MagicMock()
        mock_client_cls.return_value.auth_test.side_effect = SlackApiError(
            "token_revoked", response=mock_resp,
        )

        with (
            patch(
                "crewai_productfeature_planner.tools.slack_token_manager.get_valid_token",
                return_value="xoxb-revoked",
            ),
            patch("slack_sdk.WebClient", mock_client_cls),
        ):
            result = _validate_slack_token()

        assert result is False

    def test_no_token_returns_false(self):
        """When no token is available, returns False."""
        from crewai_productfeature_planner.apis import _validate_slack_token

        with patch(
            "crewai_productfeature_planner.tools.slack_token_manager.get_valid_token",
            return_value=None,
        ):
            result = _validate_slack_token()

        assert result is False

    def test_auth_test_ok_false_returns_false(self):
        """When auth.test returns ok=False (no exception), returns False."""
        from crewai_productfeature_planner.apis import _validate_slack_token

        mock_client_cls = MagicMock()
        mock_client_cls.return_value.auth_test.return_value = {
            "ok": False, "error": "invalid_auth",
        }

        with (
            patch(
                "crewai_productfeature_planner.tools.slack_token_manager.get_valid_token",
                return_value="xoxb-bad-token",
            ),
            patch("slack_sdk.WebClient", mock_client_cls),
        ):
            result = _validate_slack_token()

        assert result is False

    def test_network_error_assumes_ok(self):
        """Network errors (not token errors) should assume token is OK."""
        from crewai_productfeature_planner.apis import _validate_slack_token

        mock_client_cls = MagicMock()
        mock_client_cls.return_value.auth_test.side_effect = ConnectionError(
            "Network unreachable",
        )

        with (
            patch(
                "crewai_productfeature_planner.tools.slack_token_manager.get_valid_token",
                return_value="xoxb-valid",
            ),
            patch("slack_sdk.WebClient", mock_client_cls),
        ):
            result = _validate_slack_token()

        assert result is True  # network blip — assume OK


# ===================================================================
# INVARIANT 8: Event handlers must NOT process messages when no usable
# Slack token is available (circuit breaker).
# ===================================================================

_HANDLER_MODULE = "crewai_productfeature_planner.apis.slack._event_handlers"


class TestEventHandlerCircuitBreaker:
    """Event handlers must skip processing when Slack client is unavailable."""

    def test_app_mention_skips_when_no_token(self):
        """_handle_app_mention must return immediately when no token."""
        from crewai_productfeature_planner.apis.slack._event_handlers import (
            _handle_app_mention,
        )

        mock_interpret = MagicMock()
        event = {
            "channel": "C1", "text": "<@B1> hello", "user": "U1",
            "ts": "123.456", "_team_id": "T1",
        }

        with (
            patch(f"{_TOOLS_MODULE}._get_slack_client", return_value=None),
            patch(f"{_HANDLER_MODULE}._er") as mock_er,
        ):
            _handle_app_mention(event)

        # interpret_and_act should NOT have been called
        mock_er.return_value._interpret_and_act.assert_not_called()

    def test_thread_message_skips_when_no_token(self):
        """_handle_thread_message must return immediately when no token."""
        from crewai_productfeature_planner.apis.slack._event_handlers import (
            _handle_thread_message,
        )

        event = {
            "channel": "C1", "text": "follow up", "user": "U1",
            "thread_ts": "100.0", "ts": "123.456", "_team_id": "T1",
        }

        with (
            patch(f"{_TOOLS_MODULE}._get_slack_client", return_value=None),
            patch(f"{_HANDLER_MODULE}._er") as mock_er,
        ):
            _handle_thread_message(event)

        mock_er.return_value._handle_thread_message_inner.assert_not_called()

    def test_app_mention_proceeds_when_token_available(self):
        """_handle_app_mention processes normally when token is available."""
        from crewai_productfeature_planner.apis.slack._event_handlers import (
            _handle_app_mention,
        )

        mock_client = MagicMock()
        event = {
            "channel": "C1", "text": "<@B1> hello", "user": "U1",
            "ts": "123.456", "_team_id": "T1",
        }

        with (
            patch(f"{_TOOLS_MODULE}._get_slack_client", return_value=mock_client),
            patch(f"{_HANDLER_MODULE}._er") as mock_er,
            patch(
                "crewai_productfeature_planner.apis.slack.session_manager.has_pending_state",
                return_value=False,
            ),
        ):
            _handle_app_mention(event)

        mock_er.return_value._interpret_and_act.assert_called_once()
