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
    import crewai_productfeature_planner.apis.slack.session_manager as sm

    with er._thread_lock:
        er._thread_conversations.clear()
        er._thread_last_active.clear()
    with er._seen_events_lock:
        er._seen_events.clear()
    er._bot_user_id = None

    with ih._lock:
        ih._interactive_runs.clear()
        ih._manual_refinement_text.clear()

    with sm._lock:
        sm._pending_project_creates.clear()
        sm._pending_memory_entries.clear()
        sm._pending_project_setup.clear()
    yield


# ---------------------------------------------------------------------------
# Slack events_router: _interpret_and_act tracking
# ---------------------------------------------------------------------------

_EVENTS_MODULE = "crewai_productfeature_planner.apis.slack.events_router"
_TOOLS_MODULE = "crewai_productfeature_planner.tools.slack_tools"
_SESSION_MODULE = "crewai_productfeature_planner.apis.slack.session_manager"

# Default active session dict used by most tests
_ACTIVE_SESSION = {
    "project_id": "proj-default",
    "project_name": "Default Project",
    "active": True,
}


class TestInterpretAndActTracking:
    """Verify log_interaction is called from _interpret_and_act."""

    def _run_interpret(self, intent, idea=None, reply="", *, mock_log):
        """Helper: call _interpret_and_act with a mocked interpreter.

        Patches an active project session by default so that the global
        session gate does not intercept the request.
        """
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
            patch(f"{_SESSION_MODULE}.get_context_session",
                  return_value=_ACTIVE_SESSION),
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

    def test_tracking_general_question_intent(self):
        """general_question intent uses the LLM reply text."""
        mock_log = MagicMock()
        reply = "A PRD is a Product Requirements Document."
        self._run_interpret("general_question", reply=reply, mock_log=mock_log)
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "general_question"
        # The reply text from the LLM should appear in the tracked response
        assert "PRD" in kw["agent_response"]
        assert "Product Requirements Document" in kw["agent_response"]

    def test_tracking_general_question_fallback(self):
        """general_question with empty reply uses the default answer."""
        mock_log = MagicMock()
        self._run_interpret("general_question", reply="", mock_log=mock_log)
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "general_question"
        # Fallback message should mention PRDs and iteration
        assert "PRD" in kw["agent_response"]

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

        # Provide an active project session so the PRD flow path is taken
        active_session = {
            "project_id": "proj-1",
            "project_name": "Test Project",
            "active": True,
        }

        with (
            patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool",
                  return_value=mock_interpret_tool),
            patch(f"{_TOOLS_MODULE}.SlackSendMessageTool",
                  return_value=mock_send_tool),
            patch(
                "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction",
                mock_log,
            ),
            patch(f"{_SESSION_MODULE}.get_context_session",
                  return_value=active_session),
        ):
            er._interpret_and_act("C1", "T1", "U1", "create prd for fitness app", "E1")

        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "create_prd"
        assert kw["idea"] == "fitness app"
        assert kw["metadata"] is not None
        assert "interactive" in kw["metadata"]
        assert kw["project_id"] == "proj-1"

    def test_tracking_no_session_defers_any_intent(self):
        """When no project session exists, the global gate defers the request."""
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
            patch(f"{_SESSION_MODULE}.get_context_session",
                  return_value=None),
            patch(f"{_EVENTS_MODULE}._prompt_project_selection") as mock_prompt,
        ):
            er._interpret_and_act("C1", "T1", "U1", "create prd for fitness app", "E1")

        mock_prompt.assert_called_once_with("C1", "T1", "U1")
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "create_prd"
        assert kw["agent_response"] == "(project selection required)"
        assert kw["metadata"] == {"deferred_idea": "fitness app"}

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
            patch(f"{_SESSION_MODULE}.get_context_session",
                  return_value=_ACTIVE_SESSION),
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
            patch(f"{_SESSION_MODULE}.get_context_session",
                  return_value=_ACTIVE_SESSION),
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
            patch(f"{_SESSION_MODULE}.get_context_session",
                  return_value=_ACTIVE_SESSION),
        ):
            # Should NOT raise
            er._interpret_and_act("C1", "T1", "U1", "help", "E1")

        # If we get here, the test passes — no exception bubbled up
        mock_send_tool.run.assert_called_once()


# ---------------------------------------------------------------------------
# Global project-session gate
# ---------------------------------------------------------------------------


class TestGlobalSessionGate:
    """Verify that _interpret_and_act requires a project session for action intents.

    Stateless intents (help, greeting) bypass the gate and respond directly.
    The create_project intent also bypasses the gate (directly prompts for name).
    """

    def _call_with_intent(
        self, intent, *, session=None, idea=None, text="test message",
    ):
        """Call _interpret_and_act with the given intent and optional session."""
        interpretation = json.dumps({
            "intent": intent,
            "idea": idea,
            "reply": "some reply",
        })
        mock_interpret_tool = MagicMock()
        mock_interpret_tool.run.return_value = interpretation
        mock_send_tool = MagicMock()
        mock_log = MagicMock()
        mock_prompt = MagicMock()
        mock_create_project = MagicMock()

        with (
            patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool",
                  return_value=mock_interpret_tool),
            patch(f"{_TOOLS_MODULE}.SlackSendMessageTool",
                  return_value=mock_send_tool),
            patch(
                "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction",
                mock_log,
            ),
            patch(f"{_SESSION_MODULE}.get_context_session",
                  return_value=session),
            patch(f"{_EVENTS_MODULE}._prompt_project_selection", mock_prompt),
            patch(
                f"{_EVENTS_MODULE}._handle_create_project_intent",
                mock_create_project,
            ),
        ):
            er._interpret_and_act("C1", "T1", "U1", text, "E1")

        return mock_log, mock_prompt, mock_send_tool, mock_create_project

    @pytest.mark.parametrize("intent", [
        "create_prd", "publish", "check_publish", "unknown",
    ])
    def test_no_session_prompts_project_selection(self, intent):
        """Action intents trigger project-selection prompt when no session exists."""
        mock_log, mock_prompt, mock_send, _ = self._call_with_intent(
            intent, session=None,
        )
        mock_prompt.assert_called_once_with("C1", "T1", "U1")
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == intent
        assert kw["agent_response"] == "(project selection required)"

    @pytest.mark.parametrize("intent", ["help", "greeting"])
    def test_stateless_intent_bypasses_gate(self, intent):
        """Help and greeting respond even without an active session."""
        mock_log, mock_prompt, mock_send, _ = self._call_with_intent(
            intent, session=None,
        )
        mock_prompt.assert_not_called()
        mock_send.run.assert_called_once()
        # The response should include a nudge to pick a project
        sent_text = mock_send.run.call_args[1].get("text", "")
        assert "project" in sent_text.lower()

    def test_no_session_preserves_deferred_idea(self):
        """When blocking create_prd without session, the idea is tracked."""
        mock_log, mock_prompt, _, _ = self._call_with_intent(
            "create_prd", session=None, idea="fitness app",
        )
        mock_prompt.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["metadata"] == {"deferred_idea": "fitness app"}

    def test_no_session_no_deferred_idea_when_absent(self):
        """When blocking unknown intent without session, no deferred_idea metadata."""
        mock_log, _, _, _ = self._call_with_intent("unknown", session=None)
        kw = mock_log.call_args[1]
        assert kw["metadata"] is None

    @pytest.mark.parametrize("intent", [
        "help", "greeting", "unknown",
    ])
    def test_with_session_reaches_intent_handler(self, intent):
        """With an active session, intent handlers execute normally."""
        mock_log, mock_prompt, mock_send, _ = self._call_with_intent(
            intent, session=_ACTIVE_SESSION,
        )
        mock_prompt.assert_not_called()
        # The send_tool should have been called for the actual response
        mock_send.run.assert_called_once()

    # ── create_project intent ──

    def test_create_project_intent_bypasses_gate_no_session(self):
        """create_project intent triggers the create-project handler, not the gate."""
        mock_log, mock_prompt, _, mock_create = self._call_with_intent(
            "create_project", session=None,
        )
        mock_create.assert_called_once_with("C1", "T1", "U1")
        mock_prompt.assert_not_called()
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "create_project"
        assert kw["agent_response"] == "(create project prompt)"

    def test_create_project_intent_bypasses_gate_with_session(self):
        """With active session, LLM create_project intent alone falls to
        session gate (treated as unknown) — only explicit text phrases work."""
        mock_log, mock_prompt, mock_send, mock_create = self._call_with_intent(
            "create_project", session=_ACTIVE_SESSION,
        )
        # With session active, LLM intent alone does NOT trigger create_project
        mock_create.assert_not_called()

    def test_create_project_text_phrase_with_session(self):
        """With active session, explicit 'new project' phrase DOES trigger create_project."""
        mock_log, mock_prompt, _, mock_create = self._call_with_intent(
            "create_project", session=_ACTIVE_SESSION,
            text="create a new project",
        )
        mock_create.assert_called_once_with("C1", "T1", "U1")
        mock_prompt.assert_not_called()

    @pytest.mark.parametrize("text", [
        "create a project",
        "create a new project for this channel",
        "I want a new project",
        "set up a project please",
        "can you start a project",
        "create new project for this channel",
        "create new project",
        "project for this channel",
        "add new project",
        "i need a project for us",
    ])
    def test_create_project_text_fallback_no_session(self, text):
        """Text-based fallback catches 'create project' phrases even with wrong intent."""
        mock_log, mock_prompt, _, mock_create = self._call_with_intent(
            "create_prd", session=None, text=text,
        )
        mock_create.assert_called_once_with("C1", "T1", "U1")
        mock_prompt.assert_not_called()
        kw = mock_log.call_args[1]
        # Intent should be normalised to create_project
        assert kw["intent"] == "create_project"

    def test_create_prd_not_caught_by_project_fallback(self):
        """'create a PRD' should NOT match the create-project text fallback."""
        mock_log, mock_prompt, _, mock_create = self._call_with_intent(
            "create_prd", session=None, text="create a PRD for a fitness app",
        )
        # Should hit the session gate, not create-project
        mock_create.assert_not_called()
        mock_prompt.assert_called_once()

    # ── idea-phrase override ──

    @pytest.mark.parametrize("text", [
        "iterate an idea",
        "iterate a new idea",
        "new idea",
        "brainstorm an idea",
        "refine my idea",
        "help me iterate",
        "let's iterate",
        "create a prd for a chatbot",
        "plan a feature for notifications",
    ])
    def test_idea_phrase_overrides_create_project_intent(self, text):
        """When user says idea-related text, create_project intent is overridden."""
        mock_log, mock_prompt, mock_send, mock_create = self._call_with_intent(
            "create_project", session=_ACTIVE_SESSION, text=text,
        )
        # Should NOT trigger create_project
        mock_create.assert_not_called()
        # Should reach the create_prd handler (send_tool gets called)
        mock_send.run.assert_called()

    @pytest.mark.parametrize("text", [
        "iterate an idea",
        "new idea",
        "brainstorm an idea",
    ])
    def test_idea_phrase_without_session_hits_gate(self, text):
        """Idea phrases without a session go to the project-selection gate."""
        mock_log, mock_prompt, _, mock_create = self._call_with_intent(
            "create_project", session=None, text=text,
        )
        mock_create.assert_not_called()
        mock_prompt.assert_called_once()


# ---------------------------------------------------------------------------
# New intent routing (v0.1.6)
# ---------------------------------------------------------------------------


class TestNewIntentRouting:
    """Verify that the 5 new LLM intents (list_projects, switch_project,
    end_session, current_project, configure_memory) are routed correctly
    via both LLM classification and text-phrase safety net."""

    def _call_with_intent(
        self, intent, *, session=None, idea=None, text="test message",
    ):
        """Call _interpret_and_act with full handler patching."""
        interpretation = json.dumps({
            "intent": intent,
            "idea": idea,
            "reply": "some reply",
        })
        mock_interpret_tool = MagicMock()
        mock_interpret_tool.run.return_value = interpretation
        mock_send_tool = MagicMock()
        mock_log = MagicMock()
        mock_prompt = MagicMock()
        mock_create_project = MagicMock()
        mock_switch = MagicMock()
        mock_end = MagicMock()
        mock_current = MagicMock()
        mock_memory = MagicMock()

        with (
            patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool",
                  return_value=mock_interpret_tool),
            patch(f"{_TOOLS_MODULE}.SlackSendMessageTool",
                  return_value=mock_send_tool),
            patch(
                "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction",
                mock_log,
            ),
            patch(f"{_SESSION_MODULE}.get_context_session",
                  return_value=session),
            patch(f"{_EVENTS_MODULE}._prompt_project_selection", mock_prompt),
            patch(
                f"{_EVENTS_MODULE}._handle_create_project_intent",
                mock_create_project,
            ),
            patch(f"{_EVENTS_MODULE}._handle_switch_project", mock_switch),
            patch(f"{_EVENTS_MODULE}._handle_end_session", mock_end),
            patch(f"{_EVENTS_MODULE}._handle_current_project", mock_current),
            patch(f"{_EVENTS_MODULE}._handle_configure_memory", mock_memory),
            patch(f"{_SESSION_MODULE}.can_manage_memory", return_value=True),
        ):
            er._interpret_and_act("C1", "T1", "U1", text, "E1")

        return {
            "log": mock_log,
            "prompt": mock_prompt,
            "send": mock_send_tool,
            "create_project": mock_create_project,
            "switch": mock_switch,
            "end": mock_end,
            "current": mock_current,
            "memory": mock_memory,
        }

    # ── list_projects ──

    def test_list_projects_intent_triggers_prompt(self):
        """LLM list_projects intent calls _prompt_project_selection."""
        mocks = self._call_with_intent("list_projects")
        mocks["prompt"].assert_called_once_with("C1", "T1", "U1")
        kw = mocks["log"].call_args[1]
        assert kw["intent"] == "list_projects"

    def test_list_projects_intent_without_session(self):
        """list_projects works even without an active session."""
        mocks = self._call_with_intent("list_projects", session=None)
        mocks["prompt"].assert_called_once_with("C1", "T1", "U1")

    @pytest.mark.parametrize("text", [
        "show me available projects",
        "list projects",
        "what projects are there",
        "show projects please",
        "which projects exist",
        "view projects",
    ])
    def test_list_projects_text_phrase(self, text):
        """Text phrases trigger list_projects even with wrong LLM intent."""
        mocks = self._call_with_intent("unknown", text=text)
        mocks["prompt"].assert_called_once_with("C1", "T1", "U1")
        kw = mocks["log"].call_args[1]
        assert kw["intent"] == "list_projects"

    # ── switch_project ──

    def test_switch_project_intent(self):
        """LLM switch_project intent calls _handle_switch_project."""
        mocks = self._call_with_intent("switch_project")
        mocks["switch"].assert_called_once()
        kw = mocks["log"].call_args[1]
        assert kw["intent"] == "switch_project"

    @pytest.mark.parametrize("text", [
        "switch project",
        "change project",
        "use a different project",
        "switch to another project",
        "change to another project",
    ])
    def test_switch_project_text_phrase(self, text):
        """Natural phrasing triggers switch_project."""
        mocks = self._call_with_intent("unknown", text=text)
        mocks["switch"].assert_called_once()

    # ── end_session ──

    def test_end_session_intent(self):
        """LLM end_session intent calls _handle_end_session."""
        mocks = self._call_with_intent(
            "end_session", session=_ACTIVE_SESSION,
        )
        mocks["end"].assert_called_once()
        kw = mocks["log"].call_args[1]
        assert kw["intent"] == "end_session"

    @pytest.mark.parametrize("text", [
        "end session",
        "stop session",
        "close session",
        "i'm done",
    ])
    def test_end_session_text_phrase(self, text):
        """Natural phrasing triggers end_session."""
        mocks = self._call_with_intent(
            "unknown", session=_ACTIVE_SESSION, text=text,
        )
        mocks["end"].assert_called_once()

    # ── current_project ──

    def test_current_project_intent(self):
        """LLM current_project intent calls _handle_current_project."""
        mocks = self._call_with_intent(
            "current_project", session=_ACTIVE_SESSION,
        )
        mocks["current"].assert_called_once()
        kw = mocks["log"].call_args[1]
        assert kw["intent"] == "current_project"

    @pytest.mark.parametrize("text", [
        "current project",
        "my project",
        "which project",
        "what project am I on",
    ])
    def test_current_project_text_phrase(self, text):
        """Natural phrasing triggers current_project."""
        mocks = self._call_with_intent(
            "unknown", session=_ACTIVE_SESSION, text=text,
        )
        mocks["current"].assert_called_once()

    # ── configure_memory ──

    def test_configure_memory_intent(self):
        """LLM configure_memory intent calls _handle_configure_memory."""
        mocks = self._call_with_intent(
            "configure_memory", session=_ACTIVE_SESSION,
        )
        mocks["memory"].assert_called_once()
        kw = mocks["log"].call_args[1]
        assert kw["intent"] == "configure_memory"

    @pytest.mark.parametrize("text", [
        "configure memory",
        "project memory",
        "edit memory",
        "show memory",
        "update knowledge",
        "configure knowledge",
        "project knowledge",
        "edit knowledge",
        "show knowledge",
        "add knowledge",
    ])
    def test_configure_memory_text_phrase(self, text):
        """Natural phrasing triggers configure_memory."""
        mocks = self._call_with_intent(
            "unknown", session=_ACTIVE_SESSION, text=text,
        )
        mocks["memory"].assert_called_once()

    # ── idea phrase override takes priority ──

    @pytest.mark.parametrize("intent", [
        "list_projects", "switch_project", "end_session",
        "current_project", "configure_memory",
    ])
    def test_idea_phrase_overrides_new_intents(self, intent):
        """Idea phrases override management intents — routed to create_prd."""
        mocks = self._call_with_intent(
            intent, session=_ACTIVE_SESSION,
            text="iterate an idea",
        )
        # None of the management handlers should fire
        mocks["prompt"].assert_not_called()
        mocks["switch"].assert_not_called()
        mocks["end"].assert_not_called()
        mocks["current"].assert_not_called()
        mocks["memory"].assert_not_called()
        # create_prd handler (send_tool) should fire
        mocks["send"].run.assert_called()

    # ── Management intents bypass session gate ──

    @pytest.mark.parametrize("intent", [
        "list_projects", "switch_project", "end_session",
        "current_project", "configure_memory",
    ])
    def test_management_intents_bypass_session_gate(self, intent):
        """New management intents work without an active project session."""
        mocks = self._call_with_intent(intent, session=None)
        # Should NOT hit the project-selection gate for these intents
        # (prompt may be called for list_projects, but that's the handler itself)
        if intent == "list_projects":
            mocks["prompt"].assert_called_once()
        else:
            # For other intents, the handler is called directly
            handler_key = {
                "switch_project": "switch",
                "end_session": "end",
                "current_project": "current",
                "configure_memory": "memory",
            }[intent]
            mocks[handler_key].assert_called_once()


# ---------------------------------------------------------------------------
# List ideas intent routing (v0.4.1)
# ---------------------------------------------------------------------------


class TestListIdeasRouting:
    """Verify that 'list ideas' intent routes to handle_list_ideas."""

    def _call_with_intent(
        self, intent, *, session=None, text="test message",
    ):
        """Call _interpret_and_act with handle_list_ideas patched."""
        interpretation = json.dumps({
            "intent": intent,
            "idea": None,
            "reply": "some reply",
        })
        mock_interpret_tool = MagicMock()
        mock_interpret_tool.run.return_value = interpretation
        mock_send_tool = MagicMock()
        mock_log = MagicMock()
        mock_list_ideas = MagicMock()
        mock_prompt = MagicMock()

        with (
            patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool",
                  return_value=mock_interpret_tool),
            patch(f"{_TOOLS_MODULE}.SlackSendMessageTool",
                  return_value=mock_send_tool),
            patch(
                "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction",
                mock_log,
            ),
            patch(f"{_SESSION_MODULE}.get_context_session",
                  return_value=session),
            patch(f"{_EVENTS_MODULE}._handle_list_ideas", mock_list_ideas),
            patch(f"{_EVENTS_MODULE}._prompt_project_selection", mock_prompt),
        ):
            er._interpret_and_act("C1", "T1", "U1", text, "E1")

        return {
            "log": mock_log,
            "list_ideas": mock_list_ideas,
            "prompt": mock_prompt,
            "send": mock_send_tool,
        }

    def test_list_ideas_intent_routes_to_handler(self):
        """LLM list_ideas intent calls _handle_list_ideas."""
        mocks = self._call_with_intent(
            "list_ideas", session=_ACTIVE_SESSION,
        )
        mocks["list_ideas"].assert_called_once()
        kw = mocks["log"].call_args[1]
        assert kw["intent"] == "list_ideas"

    @pytest.mark.parametrize("text", [
        "list of ideas",
        "list ideas",
        "show ideas",
        "my ideas",
        "show my ideas",
        "ideas in progress",
        "current ideas",
        "what ideas",
    ])
    def test_list_ideas_text_phrase(self, text):
        """Text phrases trigger list_ideas even with wrong LLM intent."""
        mocks = self._call_with_intent(
            "unknown", session=_ACTIVE_SESSION, text=text,
        )
        mocks["list_ideas"].assert_called_once()
        kw = mocks["log"].call_args[1]
        assert kw["intent"] == "list_ideas"

    def test_list_ideas_without_session_still_routes(self):
        """list_ideas works even without an active session (handler prompts)."""
        mocks = self._call_with_intent(
            "list_ideas", session=None,
        )
        mocks["list_ideas"].assert_called_once()

    def test_list_ideas_not_confused_with_list_projects(self):
        """'list of ideas' should not trigger list_projects."""
        mocks = self._call_with_intent(
            "unknown", session=_ACTIVE_SESSION, text="list of ideas",
        )
        mocks["list_ideas"].assert_called_once()
        mocks["prompt"].assert_not_called()


# ---------------------------------------------------------------------------
# Project setup wizard
# ---------------------------------------------------------------------------


class TestProjectSetupWizard:
    """Verify the multi-step project setup flow (confluence/jira keys)."""

    def test_mark_and_get_pending_setup(self):
        from crewai_productfeature_planner.apis.slack.session_manager import (
            get_pending_setup,
            mark_pending_setup,
            pop_pending_setup,
        )

        mark_pending_setup("U1", "C1", "T1", "proj1", "My Project")
        entry = get_pending_setup("U1")
        assert entry is not None
        assert entry["step"] == "confluence_space_key"
        assert entry["project_id"] == "proj1"

        # Pop removes it
        popped = pop_pending_setup("U1")
        assert popped is not None
        assert get_pending_setup("U1") is None

    def test_advance_through_all_steps(self):
        from crewai_productfeature_planner.apis.slack.session_manager import (
            advance_pending_setup,
            get_pending_setup,
            mark_pending_setup,
        )

        mark_pending_setup("U1", "C1", "T1", "proj1", "Test")

        # Step 1: confluence_space_key
        entry = advance_pending_setup("U1", "ENG")
        assert entry["confluence_space_key"] == "ENG"
        assert entry["step"] == "jira_project_key"

        # Step 2: jira_project_key
        entry = advance_pending_setup("U1", "FEAT")
        assert entry["jira_project_key"] == "FEAT"
        assert entry["step"] == "figma_api_key"

        # Step 3: figma_api_key
        entry = advance_pending_setup("U1", "figd_test123")
        assert entry["figma_api_key"] == "figd_test123"
        assert entry["step"] == "figma_team_id"

        # Step 4: figma_team_id
        entry = advance_pending_setup("U1", "99999")
        assert entry["figma_team_id"] == "99999"
        assert entry["step"] == "done"

        # After done, the entry is removed
        assert get_pending_setup("U1") is None

    def test_advance_with_skips(self):
        from crewai_productfeature_planner.apis.slack.session_manager import (
            advance_pending_setup,
            mark_pending_setup,
        )

        mark_pending_setup("U1", "C1", "T1", "proj1", "Test")
        advance_pending_setup("U1", "")  # skip confluence
        advance_pending_setup("U1", "")  # skip jira
        advance_pending_setup("U1", "")  # skip figma api key
        entry = advance_pending_setup("U1", "")  # skip figma team id
        assert entry["step"] == "done"
        assert entry["confluence_space_key"] == ""
        assert entry["jira_project_key"] == ""
        assert entry["figma_api_key"] == ""
        assert entry["figma_team_id"] == ""

    def test_has_pending_state_includes_setup(self):
        from crewai_productfeature_planner.apis.slack.session_manager import (
            has_pending_state,
            mark_pending_setup,
            pop_pending_setup,
        )

        assert not has_pending_state("U1")
        mark_pending_setup("U1", "C1", "T1", "proj1", "Test")
        assert has_pending_state("U1")
        pop_pending_setup("U1")
        assert not has_pending_state("U1")

    def test_handle_project_setup_reply_advances_and_posts(self):
        """_handle_project_setup_reply should advance the wizard and post next step."""
        from crewai_productfeature_planner.apis.slack.session_manager import (
            get_pending_setup,
            mark_pending_setup,
        )

        mark_pending_setup("U1", "C1", "T1", "proj1", "Test")

        with patch(f"{_TOOLS_MODULE}._get_slack_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client_fn.return_value = mock_client
            er._handle_project_setup_reply("C1", "T1", "U1", "ENG")

        # Should have advanced to next step
        entry = get_pending_setup("U1")
        assert entry is not None
        assert entry["step"] == "jira_project_key"
        assert entry["confluence_space_key"] == "ENG"
        mock_client.chat_postMessage.assert_called_once()

    def test_handle_project_setup_skip(self):
        """Typing 'skip' stores empty string for the current step."""
        from crewai_productfeature_planner.apis.slack.session_manager import (
            get_pending_setup,
            mark_pending_setup,
        )

        mark_pending_setup("U1", "C1", "T1", "proj1", "Test")

        with patch(f"{_TOOLS_MODULE}._get_slack_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client_fn.return_value = mock_client
            er._handle_project_setup_reply("C1", "T1", "U1", "skip")

        entry = get_pending_setup("U1")
        assert entry["confluence_space_key"] == ""
        assert entry["step"] == "jira_project_key"

    def test_handle_project_setup_completes_and_activates(self):
        """After all steps, session is activated and summary is posted."""
        from crewai_productfeature_planner.apis.slack.session_manager import (
            get_pending_setup,
            mark_pending_setup,
        )

        mark_pending_setup("U1", "C1", "T1", "proj1", "Test")

        with (
            patch(f"{_TOOLS_MODULE}._get_slack_client") as mock_client_fn,
            patch(
                "crewai_productfeature_planner.mongodb.project_config.update_project"
            ) as mock_update,
            patch(
                f"{_SESSION_MODULE}.activate_channel_project"
            ) as mock_activate,
            patch(f"{_SESSION_MODULE}.is_dm", return_value=False),
        ):
            mock_client = MagicMock()
            mock_client_fn.return_value = mock_client

            # Step through all 4 steps
            er._handle_project_setup_reply("C1", "T1", "U1", "ENG")
            er._handle_project_setup_reply("C1", "T1", "U1", "FEAT")
            er._handle_project_setup_reply("C1", "T1", "U1", "figd_key")
            er._handle_project_setup_reply("C1", "T1", "U1", "99999")

        # Entry should be cleared
        assert get_pending_setup("U1") is None

        # Project config should be updated with the keys
        mock_update.assert_called_once_with(
            "proj1",
            name="Test",
            confluence_space_key="ENG",
            jira_project_key="FEAT",
            figma_api_key="figd_key",
            figma_team_id="99999",
        )

        # Channel session should be activated
        mock_activate.assert_called_once_with(
            channel_id="C1",
            project_id="proj1",
            project_name="Test",
            activated_by="U1",
        )

    def test_setup_blocks_contain_step_label(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            project_setup_step_blocks,
        )

        blocks = project_setup_step_blocks("My Project", "jira_project_key", 2, 4)
        text = blocks[0]["text"]["text"]
        assert "Jira Project Key" in text
        assert "step 2/4" in text

    def test_setup_complete_blocks_show_keys(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            project_setup_complete_blocks,
        )

        blocks = project_setup_complete_blocks("My Project", {
            "confluence_space_key": "ENG",
            "jira_project_key": "FEAT",
            "figma_api_key": "figd_longkey123",
            "figma_team_id": "99999",
        })
        text = blocks[0]["text"]["text"]
        assert "ENG" in text
        assert "FEAT" in text
        assert "figd_lon…" in text
        assert "99999" in text
        assert "set up and ready" in text

    def test_reconfig_wizard_starts_at_project_name(self):
        """mark_pending_reconfig should start at project_name step with existing values."""
        from crewai_productfeature_planner.apis.slack.session_manager import (
            get_pending_setup,
            mark_pending_reconfig,
            pop_pending_setup,
        )

        existing = {
            "name": "Old Name",
            "confluence_space_key": "ENG",
            "jira_project_key": "FEAT",
            "figma_api_key": "figd_old",
            "figma_team_id": "11111",
        }
        mark_pending_reconfig("U1", "C1", "T1", "proj1", existing)
        entry = get_pending_setup("U1")
        assert entry is not None
        assert entry["step"] == "project_name"
        assert entry["project_name"] == "Old Name"
        assert entry["confluence_space_key"] == "ENG"
        assert entry["figma_api_key"] == "figd_old"
        pop_pending_setup("U1")

    def test_reconfig_advance_through_all_5_steps(self):
        """Reconfig wizard should walk through all 5 steps including project_name."""
        from crewai_productfeature_planner.apis.slack.session_manager import (
            advance_pending_setup,
            get_pending_setup,
            mark_pending_reconfig,
        )

        existing = {"name": "Old", "confluence_space_key": "", "jira_project_key": "",
                     "figma_api_key": "", "figma_team_id": ""}
        mark_pending_reconfig("U1", "C1", "T1", "proj1", existing)

        # Step 1: project_name
        entry = advance_pending_setup("U1", "New Name")
        assert entry["project_name"] == "New Name"
        assert entry["step"] == "confluence_space_key"

        # Step 2: confluence_space_key
        entry = advance_pending_setup("U1", "NEWENG")
        assert entry["confluence_space_key"] == "NEWENG"
        assert entry["step"] == "jira_project_key"

        # Step 3: jira_project_key
        entry = advance_pending_setup("U1", "NEWPROJ")
        assert entry["jira_project_key"] == "NEWPROJ"
        assert entry["step"] == "figma_api_key"

        # Step 4: figma_api_key
        entry = advance_pending_setup("U1", "figd_new")
        assert entry["figma_api_key"] == "figd_new"
        assert entry["step"] == "figma_team_id"

        # Step 5: figma_team_id
        entry = advance_pending_setup("U1", "22222")
        assert entry["figma_team_id"] == "22222"
        assert entry["step"] == "done"

        assert get_pending_setup("U1") is None

    def test_setup_step_blocks_show_current_value(self):
        """project_setup_step_blocks should display current_value when given."""
        from crewai_productfeature_planner.apis.slack.blocks import (
            project_setup_step_blocks,
        )

        blocks = project_setup_step_blocks(
            "My Project", "confluence_space_key", 2, 5,
            current_value="ENG",
        )
        text = blocks[0]["text"]["text"]
        assert "Current value:" in text
        assert "ENG" in text

    def test_setup_step_blocks_project_name_label(self):
        """project_setup_step_blocks should show Project Name label."""
        from crewai_productfeature_planner.apis.slack.blocks import (
            project_setup_step_blocks,
        )

        blocks = project_setup_step_blocks("My Project", "project_name", 1, 5)
        text = blocks[0]["text"]["text"]
        assert "Project Name" in text
        assert "step 1/5" in text

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
