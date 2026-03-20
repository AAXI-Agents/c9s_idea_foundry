"""Tests for the update_config intent classification — bare 'configure' phrase."""

import json
from unittest.mock import MagicMock, patch

import pytest

_EVENTS_MODULE = "crewai_productfeature_planner.apis.slack.events_router"
_SESSION_MODULE = "crewai_productfeature_planner.apis.slack.session_manager"
_TOOLS_MODULE = "crewai_productfeature_planner.tools.slack_tools"

_ACTIVE_SESSION = {
    "project_id": "proj-1",
    "project_name": "Test Project",
    "active": True,
}


def _make_mocks(intent, reply="", idea=None):
    interpretation = json.dumps({"intent": intent, "idea": idea, "reply": reply})
    mock_interpret = MagicMock()
    mock_interpret.run.return_value = interpretation
    mock_send = MagicMock()
    return mock_interpret, mock_send


class TestUpdateConfigPhraseDetection:
    """Verify phrase-level detection catches project configuration phrases."""

    def test_phrase_fallback_returns_update_config_for_bare_configure(self):
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _phrase_fallback,
        )

        result = _phrase_fallback("configure")
        assert result["intent"] == "update_config"

    def test_phrase_fallback_returns_update_config_for_config_phrases(self):
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _phrase_fallback,
        )

        for phrase in (
            "configure project",
            "project config",
            "reconfigure",
            "update config",
        ):
            result = _phrase_fallback(phrase)
            assert result["intent"] == "update_config", (
                f"Phrase '{phrase}' did not match update_config, "
                f"got {result['intent']}"
            )

    def test_configure_memory_still_wins_over_configure(self):
        """'configure memory' should still match configure_memory, not update_config."""
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _phrase_fallback,
        )

        result = _phrase_fallback("configure memory")
        assert result["intent"] == "configure_memory"


class TestUpdateConfigPhraseOverride:
    """Verify phrase override routes bare 'configure' to update_config handler."""

    @patch(f"{_EVENTS_MODULE}._handle_update_config")
    def test_bare_configure_dispatches_to_update_config(self, mock_handler):
        """Bare 'configure' should trigger project config handler."""
        import crewai_productfeature_planner.apis.slack.events_router as er

        mock_interpret, mock_send = _make_mocks("unknown")

        with (
            patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool",
                  return_value=mock_interpret),
            patch(f"{_TOOLS_MODULE}.SlackSendMessageTool",
                  return_value=mock_send),
            patch(
                "crewai_productfeature_planner.mongodb.agent_interactions"
                ".repository.log_interaction",
                MagicMock(),
            ),
            patch(f"{_SESSION_MODULE}.get_context_session",
                  return_value=_ACTIVE_SESSION),
        ):
            er._interpret_and_act("C1", "T1", "U1", "configure", "E1")

        mock_handler.assert_called_once()

    @patch(f"{_EVENTS_MODULE}._handle_update_config")
    def test_llm_returns_update_config_dispatches(self, mock_handler):
        """LLM correctly classifies as update_config → handler fires."""
        import crewai_productfeature_planner.apis.slack.events_router as er

        mock_interpret, mock_send = _make_mocks("update_config")

        with (
            patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool",
                  return_value=mock_interpret),
            patch(f"{_TOOLS_MODULE}.SlackSendMessageTool",
                  return_value=mock_send),
            patch(
                "crewai_productfeature_planner.mongodb.agent_interactions"
                ".repository.log_interaction",
                MagicMock(),
            ),
            patch(f"{_SESSION_MODULE}.get_context_session",
                  return_value=_ACTIVE_SESSION),
        ):
            er._interpret_and_act("C1", "T1", "U1", "configure", "E1")

        mock_handler.assert_called_once()
