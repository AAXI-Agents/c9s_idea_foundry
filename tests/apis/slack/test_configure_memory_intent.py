"""Tests for the configure_memory intent classification and phrase override."""

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


class TestConfigureMemoryPhraseDetection:
    """Verify phrase-level detection catches memory configuration phrases."""

    def test_phrase_fallback_returns_configure_memory(self):
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _phrase_fallback,
        )

        for phrase in (
            "configure memory", "configure more memory",
            "project memory", "setup memory", "memory config",
            "edit memory", "update memory", "view memory",
            "show memory", "add memory", "manage memory",
            "configure knowledge", "knowledge config",
            "add knowledge", "manage knowledge",
        ):
            result = _phrase_fallback(phrase)
            assert result["intent"] == "configure_memory", (
                f"Phrase '{phrase}' did not match configure_memory, "
                f"got {result['intent']}"
            )


class TestConfigureMemoryPhraseOverride:
    """Verify phrase override corrects LLM misclassification."""

    @patch(f"{_EVENTS_MODULE}._handle_configure_memory")
    def test_llm_returns_list_ideas_but_phrase_overrides(self, mock_handler):
        """Regression: LLM classified 'configure memory' as list_ideas."""
        import crewai_productfeature_planner.apis.slack.events_router as er

        # LLM incorrectly returns "list_ideas" for "configure memory"
        mock_interpret, mock_send = _make_mocks("list_ideas")

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
            patch(f"{_SESSION_MODULE}.can_manage_memory", return_value=True),
        ):
            er._interpret_and_act("C1", "T1", "U1", "configure memory", "E1")

        mock_handler.assert_called_once()

    @patch(f"{_EVENTS_MODULE}._handle_configure_memory")
    def test_llm_returns_unknown_but_phrase_overrides(self, mock_handler):
        """Even if LLM returns 'unknown', the phrase override should fix it."""
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
            patch(f"{_SESSION_MODULE}.can_manage_memory", return_value=True),
        ):
            er._interpret_and_act("C1", "T1", "U1", "setup memory", "E1")

        mock_handler.assert_called_once()

    @patch(f"{_EVENTS_MODULE}._handle_configure_memory")
    def test_correct_intent_dispatches(self, mock_handler):
        """When LLM correctly returns configure_memory, it dispatches."""
        import crewai_productfeature_planner.apis.slack.events_router as er

        mock_interpret, mock_send = _make_mocks("configure_memory")

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
            patch(f"{_SESSION_MODULE}.can_manage_memory", return_value=True),
        ):
            er._interpret_and_act(
                "C1", "T1", "U1", "configure memory", "E1",
            )

        mock_handler.assert_called_once()

    def test_admin_gate_blocks_non_admin(self):
        """Non-admin users get the lock message instead of memory config."""
        import crewai_productfeature_planner.apis.slack.events_router as er

        mock_interpret, mock_send = _make_mocks("configure_memory")
        mock_reply = MagicMock()

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
            patch(f"{_SESSION_MODULE}.can_manage_memory", return_value=False),
            patch(f"{_EVENTS_MODULE}._reply", mock_reply),
        ):
            er._interpret_and_act(
                "C1", "T1", "U1", "configure memory", "E1",
            )

        # Should have sent the admin-required message via _reply
        mock_reply.assert_called_once()
        assert ":lock:" in mock_reply.call_args[0][2]


class TestUpdateConfigPhraseOverride:
    """Verify update_config phrase override corrects LLM misclassification."""

    @patch(f"{_EVENTS_MODULE}._handle_update_config")
    def test_llm_returns_general_question_but_phrase_overrides(self, mock_handler):
        """LLM may misclassify 'confluence key' — phrase override catches it."""
        import crewai_productfeature_planner.apis.slack.events_router as er

        mock_interpret, mock_send = _make_mocks("general_question")

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
            er._interpret_and_act(
                "C1", "T1", "U1", "set confluence key", "E1",
            )

        mock_handler.assert_called_once()


class TestCreateIdeaPhraseDetection:
    """Verify 'create idea' variants are detected as create_prd."""

    def test_phrase_fallback_returns_create_prd(self):
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _phrase_fallback,
        )

        for phrase in (
            "create idea", "create an idea",
            "create new idea", "create a new idea",
        ):
            result = _phrase_fallback(phrase)
            assert result["intent"] == "create_prd", (
                f"Phrase '{phrase}' did not match create_prd, "
                f"got {result['intent']}"
            )

    def test_create_idea_overrides_configure_memory_llm(self):
        """Regression: LLM classified 'create idea' as configure_memory."""
        import crewai_productfeature_planner.apis.slack.events_router as er

        # LLM incorrectly returns configure_memory for "create idea"
        mock_interpret, mock_send = _make_mocks(
            "configure_memory", idea=None,
        )

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
            patch(f"{_SESSION_MODULE}.can_manage_memory", return_value=True),
            patch(f"{_EVENTS_MODULE}._handle_configure_memory") as mock_mem_handler,
        ):
            er._interpret_and_act("C1", "T1", "U1", "create idea", "E1")

        # configure_memory handler should NOT be called
        mock_mem_handler.assert_not_called()
        # send_tool should have been called (for create_prd ask/ack)
        mock_send.run.assert_called()
