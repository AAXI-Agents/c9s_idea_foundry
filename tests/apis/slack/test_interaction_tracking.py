"""Tests for agent interaction tracking in Slack events and interactive handlers."""

import json
import threading
from unittest.mock import MagicMock, patch, call

import pytest

from crewai_productfeature_planner.apis.slack import events_router as er
from crewai_productfeature_planner.apis.slack import interactive_handlers as ih


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")


@pytest.fixture(autouse=True)
def _clean_state():
    """Clear module-level caches between tests."""
    with er._thread_lock:
        er._thread_conversations.clear()
        er._thread_last_active.clear()
    with er._seen_events_lock:
        er._seen_events.clear()
    er._bot_user_id = None

    with ih._lock:
        ih._interactive_runs.clear()
        ih._manual_refinement_text.clear()
    yield


# ---------------------------------------------------------------------------
# Slack events_router: _interpret_and_act tracking
# ---------------------------------------------------------------------------

_EVENTS_MODULE = "crewai_productfeature_planner.apis.slack.events_router"
_TOOLS_MODULE = "crewai_productfeature_planner.tools.slack_tools"


class TestInterpretAndActTracking:
    """Verify log_interaction is called from _interpret_and_act."""

    def _run_interpret(self, intent, idea=None, reply="", *, mock_log):
        """Helper: call _interpret_and_act with a mocked interpreter."""
        interpretation = json.dumps({"intent": intent, "idea": idea, "reply": reply})
        mock_interpret_tool = MagicMock()
        mock_interpret_tool.run.return_value = interpretation
        mock_send_tool = MagicMock()

        with (
            patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool",
                  return_value=mock_interpret_tool),
            patch(f"{_TOOLS_MODULE}.SlackSendMessageTool",
                  return_value=mock_send_tool),
            patch(
                "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction",
                mock_log,
            ),
        ):
            er._interpret_and_act("C1", "T1", "U1", "hello", "E1")

        return mock_send_tool

    def test_tracking_help_intent(self):
        mock_log = MagicMock()
        self._run_interpret("help", mock_log=mock_log)
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["source"] == "slack"
        assert kw["intent"] == "help"
        assert kw["user_message"] == "hello"
        assert kw["user_id"] == "U1"
        assert kw["channel"] == "C1"
        assert kw["thread_ts"] == "T1"

    def test_tracking_greeting_intent(self):
        mock_log = MagicMock()
        self._run_interpret("greeting", reply="Hey!", mock_log=mock_log)
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "greeting"
        assert "Hey!" in kw["agent_response"] or "<@U1>" in kw["agent_response"]

    def test_tracking_create_prd_no_idea(self):
        mock_log = MagicMock()
        self._run_interpret("create_prd", mock_log=mock_log)
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "create_prd"
        assert kw["idea"] is None

    @patch(f"{_EVENTS_MODULE}._kick_off_prd_flow")
    def test_tracking_create_prd_with_idea(self, mock_kickoff):
        mock_log = MagicMock()
        interpretation = json.dumps({
            "intent": "create_prd",
            "idea": "fitness app",
            "reply": "",
        })
        mock_interpret_tool = MagicMock()
        mock_interpret_tool.run.return_value = interpretation
        mock_send_tool = MagicMock()

        with (
            patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool",
                  return_value=mock_interpret_tool),
            patch(f"{_TOOLS_MODULE}.SlackSendMessageTool",
                  return_value=mock_send_tool),
            patch(
                "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction",
                mock_log,
            ),
        ):
            er._interpret_and_act("C1", "T1", "U1", "create prd for fitness app", "E1")

        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "create_prd"
        assert kw["idea"] == "fitness app"
        assert kw["metadata"] is not None
        assert "interactive" in kw["metadata"]

    def test_tracking_unknown_intent(self):
        mock_log = MagicMock()
        self._run_interpret("unknown", reply="I don't understand", mock_log=mock_log)
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "unknown"

    def test_tracking_publish_intent(self):
        mock_log = MagicMock()
        interpretation = json.dumps({
            "intent": "publish",
            "idea": None,
            "reply": "",
        })
        mock_interpret_tool = MagicMock()
        mock_interpret_tool.run.return_value = interpretation
        mock_send_tool = MagicMock()

        with (
            patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool",
                  return_value=mock_interpret_tool),
            patch(f"{_TOOLS_MODULE}.SlackSendMessageTool",
                  return_value=mock_send_tool),
            patch(f"{_EVENTS_MODULE}._handle_publish_intent"),
            patch(
                "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction",
                mock_log,
            ),
        ):
            er._interpret_and_act("C1", "T1", "U1", "publish all", "E1")

        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "publish"

    def test_tracking_check_publish_intent(self):
        mock_log = MagicMock()
        interpretation = json.dumps({
            "intent": "check_publish",
            "idea": None,
            "reply": "",
        })
        mock_interpret_tool = MagicMock()
        mock_interpret_tool.run.return_value = interpretation
        mock_send_tool = MagicMock()

        with (
            patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool",
                  return_value=mock_interpret_tool),
            patch(f"{_TOOLS_MODULE}.SlackSendMessageTool",
                  return_value=mock_send_tool),
            patch(f"{_EVENTS_MODULE}._handle_check_publish_intent"),
            patch(
                "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction",
                mock_log,
            ),
        ):
            er._interpret_and_act("C1", "T1", "U1", "check publish status", "E1")

        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "check_publish"

    def test_tracking_failure_does_not_crash(self):
        """If log_interaction raises, _interpret_and_act should NOT crash."""
        interpretation = json.dumps({
            "intent": "help",
            "idea": None,
            "reply": "",
        })
        mock_interpret_tool = MagicMock()
        mock_interpret_tool.run.return_value = interpretation
        mock_send_tool = MagicMock()

        with (
            patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool",
                  return_value=mock_interpret_tool),
            patch(f"{_TOOLS_MODULE}.SlackSendMessageTool",
                  return_value=mock_send_tool),
            patch(
                "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction",
                side_effect=RuntimeError("DB down"),
            ),
        ):
            # Should NOT raise
            er._interpret_and_act("C1", "T1", "U1", "help", "E1")

        # If we get here, the test passes — no exception bubbled up
        mock_send_tool.run.assert_called_once()


# ---------------------------------------------------------------------------
# Interactive handlers: resolve_interaction tracking
# ---------------------------------------------------------------------------

_IH_MODULE = "crewai_productfeature_planner.apis.slack.interactive_handlers"


class TestResolveInteractionTracking:
    """Verify log_interaction is called from resolve_interaction."""

    def test_tracking_on_resolve(self):
        ih.register_interactive_run("run1", "C1", "T1", "U1", "test idea")
        with ih._lock:
            ih._interactive_runs["run1"]["pending_action"] = "idea_approval"

        with patch(
            "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction"
        ) as mock_log:
            result = ih.resolve_interaction("run1", "idea_approve", "U1")

        assert result is True
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["source"] == "slack_interactive"
        assert kw["user_message"] == "idea_approve"
        assert kw["intent"] == "idea_approval"
        assert kw["run_id"] == "run1"
        assert kw["user_id"] == "U1"
        assert kw["metadata"]["action_id"] == "idea_approve"

    def test_no_tracking_when_run_not_found(self):
        with patch(
            "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction"
        ) as mock_log:
            result = ih.resolve_interaction("nonexistent", "idea_approve", "U1")

        assert result is False
        mock_log.assert_not_called()

    def test_tracking_failure_does_not_crash(self):
        ih.register_interactive_run("run2", "C1", "T1", "U1", "test idea")
        with ih._lock:
            ih._interactive_runs["run2"]["pending_action"] = "refinement_mode"

        with patch(
            "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction",
            side_effect=RuntimeError("DB down"),
        ):
            result = ih.resolve_interaction("run2", "refinement_agent", "U1")

        # Should succeed despite tracking failure
        assert result is True


# ---------------------------------------------------------------------------
# Interactive handlers: submit_manual_refinement tracking
# ---------------------------------------------------------------------------


class TestManualRefinementTracking:
    """Verify log_interaction is called from submit_manual_refinement."""

    def test_tracking_on_submit(self):
        ih.register_interactive_run("run3", "C1", "T1", "U1", "test idea")
        with ih._lock:
            ih._interactive_runs["run3"]["pending_action"] = "manual_refinement"

        with patch(
            "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction"
        ) as mock_log:
            result = ih.submit_manual_refinement("run3", "revised idea text")

        assert result is True
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["source"] == "slack_interactive"
        assert kw["user_message"] == "revised idea text"
        assert kw["intent"] == "manual_refinement"
        assert kw["run_id"] == "run3"

    def test_no_tracking_when_run_not_found(self):
        with patch(
            "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction"
        ) as mock_log:
            result = ih.submit_manual_refinement("nonexistent", "text")

        assert result is False
        mock_log.assert_not_called()
