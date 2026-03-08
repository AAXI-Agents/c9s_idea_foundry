"""Tests for the create_jira intent classification and phrase fallback."""

import json
from unittest.mock import MagicMock, patch

_EVENTS_MODULE = "crewai_productfeature_planner.apis.slack.events_router"
_SESSION_MODULE = "crewai_productfeature_planner.apis.slack.session_manager"
_TOOLS_MODULE = "crewai_productfeature_planner.tools.slack_tools"

_ACTIVE_SESSION = {
    "project_id": "proj-1",
    "project_name": "Test Project",
    "active": True,
}


def _make_mocks(intent, reply="", idea=None):
    """Create mocked interpret and send tools returning the given intent."""
    interpretation = json.dumps({"intent": intent, "idea": idea, "reply": reply})
    mock_interpret = MagicMock()
    mock_interpret.run.return_value = interpretation
    mock_send = MagicMock()
    return mock_interpret, mock_send


class TestCreateJiraPhraseDetection:
    """Verify phrase-level detection catches 'create jira' without LLM."""

    def test_phrase_fallback_returns_create_jira(self):
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _phrase_fallback,
        )

        for phrase in ("create jira", "jira tickets", "create jira tickets",
                       "make jira tickets", "generate jira", "jira skeleton"):
            result = _phrase_fallback(phrase)
            assert result["intent"] == "create_jira", (
                f"Phrase '{phrase}' did not match create_jira, got {result['intent']}"
            )

    def test_publish_does_not_match_create_jira(self):
        """The 'publish' phrase should NOT match create_jira."""
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _phrase_fallback,
        )
        result = _phrase_fallback("publish")
        assert result["intent"] != "create_jira"


class TestCreateJiraIntentDispatch:
    """Verify the message handler dispatches create_jira to the correct handler."""

    @patch(f"{_EVENTS_MODULE}._handle_create_jira_intent")
    def test_create_jira_intent_dispatches(self, mock_handler):
        import crewai_productfeature_planner.apis.slack.events_router as er

        mock_interpret, mock_send = _make_mocks("create_jira")

        with (
            patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool",
                  return_value=mock_interpret),
            patch(f"{_TOOLS_MODULE}.SlackSendMessageTool",
                  return_value=mock_send),
            patch(
                "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction",
                MagicMock(),
            ),
            patch(f"{_SESSION_MODULE}.get_context_session",
                  return_value=_ACTIVE_SESSION),
        ):
            er._interpret_and_act("C1", "T1", "U1", "create jira", "E1")

        mock_handler.assert_called_once_with("C1", "T1", "U1", mock_send)

    @patch(f"{_EVENTS_MODULE}._handle_create_jira_intent")
    def test_phrase_override_triggers_create_jira(self, mock_handler):
        """Even if LLM returns 'publish', the phrase override should fix it."""
        import crewai_productfeature_planner.apis.slack.events_router as er

        # LLM incorrectly returns "publish" for "create jira tickets"
        mock_interpret, mock_send = _make_mocks("publish")

        with (
            patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool",
                  return_value=mock_interpret),
            patch(f"{_TOOLS_MODULE}.SlackSendMessageTool",
                  return_value=mock_send),
            patch(
                "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction",
                MagicMock(),
            ),
            patch(f"{_SESSION_MODULE}.get_context_session",
                  return_value=_ACTIVE_SESSION),
        ):
            er._interpret_and_act("C1", "T1", "U1", "create jira tickets", "E1")

        # The phrase-level override should catch "create jira tickets"
        mock_handler.assert_called_once()


class TestCreateJiraHandlerProxy:
    """Verify handler proxy wiring."""

    def test_proxy_calls_events_router(self):
        from crewai_productfeature_planner.apis.slack._handler_proxies import (
            _handle_create_jira_intent,
        )

        with patch(
            f"{_EVENTS_MODULE}._handle_create_jira_intent",
        ) as mock:
            _handle_create_jira_intent("C1", "T1", "U1", MagicMock())
            mock.assert_called_once()
