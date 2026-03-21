"""Tests for the configure_memory intent classification and phrase override."""

import json
from unittest.mock import MagicMock, patch

import pytest

import crewai_productfeature_planner.apis.slack.session_manager as sm

_EVENTS_MODULE = "crewai_productfeature_planner.apis.slack.events_router"
_SESSION_MODULE = "crewai_productfeature_planner.apis.slack.session_manager"
_TOOLS_MODULE = "crewai_productfeature_planner.tools.slack_tools"


@pytest.fixture(autouse=True)
def _clear_pending_memory():
    """Ensure pending-memory entries don't leak between tests."""
    sm._pending_memory_entries.clear()
    yield
    sm._pending_memory_entries.clear()

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
            patch(f"{_SESSION_MODULE}.can_manage_memory", return_value=True),
        ):
            er._interpret_and_act(
                "C1", "T1", "U1", "set confluence key", "E1",
            )

        mock_handler.assert_called_once()

    @patch(f"{_EVENTS_MODULE}._handle_update_config")
    def test_project_config_phrase_triggers_update_config(self, mock_handler):
        """Phrases like 'project config' should trigger update_config intent."""
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
            patch(f"{_SESSION_MODULE}.can_manage_memory", return_value=True),
        ):
            er._interpret_and_act(
                "C1", "T1", "U1", "project config", "E1",
            )

        mock_handler.assert_called_once()


class TestConfigPhraseFallback:
    """Verify new config phrases resolve to update_config in phrase fallback."""

    def test_new_config_phrases(self):
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _phrase_fallback,
        )

        for phrase in (
            "project config", "project configuration",
            "configure project", "reconfigure", "project settings",
            "edit config", "update project config",
        ):
            result = _phrase_fallback(phrase)
            assert result["intent"] == "update_config", (
                f"Phrase '{phrase}' did not match update_config, "
                f"got {result['intent']}"
            )


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


class TestLlmIsPrimaryClassifier:
    """Verify the LLM is trusted for memory/config intents — phrase matching
    does NOT override the LLM for these ambiguous intents."""

    def test_idea_with_memory_substring_trusts_llm(self):
        """LLM says create_prd for 'a feature to update memory caching' —
        the phrase override must NOT force configure_memory even though
        'update memory' is a memory phrase substring."""
        import crewai_productfeature_planner.apis.slack.events_router as er

        mock_interpret, mock_send = _make_mocks(
            "create_prd", idea="a feature to update memory caching",
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
            patch(f"{_EVENTS_MODULE}._handle_configure_memory") as mock_mem,
            patch(f"{_EVENTS_MODULE}._kick_off_prd_flow") as mock_flow,
        ):
            er._interpret_and_act(
                "C1", "T1", "U1",
                "iterate an idea for a feature to update memory caching",
                "E1",
            )

        # LLM classification (create_prd) should be respected
        mock_mem.assert_not_called()
        mock_send.run.assert_called()

    def test_idea_with_knowledge_substring_trusts_llm(self):
        """LLM says create_prd for 'add knowledge sharing' — the phrase
        'add knowledge' must NOT force configure_memory."""
        import crewai_productfeature_planner.apis.slack.events_router as er

        mock_interpret, mock_send = _make_mocks(
            "create_prd", idea="add knowledge sharing to the platform",
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
            patch(f"{_EVENTS_MODULE}._handle_configure_memory") as mock_mem,
        ):
            er._interpret_and_act(
                "C1", "T1", "U1",
                "iterate an idea to add knowledge sharing to the platform",
                "E1",
            )

        mock_mem.assert_not_called()
        mock_send.run.assert_called()


class TestPendingMemoryCommandDetection:
    """Verify that when the thread is in pending_memory state, command
    phrases cancel memory mode and route to intent classification."""

    def test_create_idea_cancels_pending_memory(self):
        """Typing 'create idea' while in pending_memory state should
        cancel memory mode and route to intent classification."""
        import crewai_productfeature_planner.apis.slack.events_router as er
        from crewai_productfeature_planner.apis.slack.session_manager import (
            mark_pending_memory,
        )

        mark_pending_memory("U1", "C1", "T1", "idea_iteration", "proj-1")

        with (
            patch.object(er, "handle_memory_reply") as mock_mem_reply,
            patch.object(er, "_interpret_and_act") as mock_interpret,
            patch.object(er, "touch_thread"),
            patch(f"{_SESSION_MODULE}.pop_pending_create", return_value=None),
            patch(f"{_SESSION_MODULE}.get_pending_create_owner_for_thread",
                  return_value=None),
            patch(f"{_SESSION_MODULE}.get_pending_setup", return_value=None),
        ):
            er._handle_thread_message_inner(
                "C1", "T1", "U1", "create idea", "E1",
            )

        # Memory handler should NOT be called
        mock_mem_reply.assert_not_called()
        # Should fall through to intent classification
        mock_interpret.assert_called_once()

    def test_iterate_idea_cancels_pending_memory(self):
        """Typing 'iterate an idea' while in pending_memory cancels it."""
        import crewai_productfeature_planner.apis.slack.events_router as er
        from crewai_productfeature_planner.apis.slack.session_manager import (
            mark_pending_memory,
        )

        mark_pending_memory("U1", "C1", "T1", "knowledge", "proj-1")

        with (
            patch.object(er, "handle_memory_reply") as mock_mem_reply,
            patch.object(er, "_interpret_and_act") as mock_interpret,
            patch.object(er, "touch_thread"),
            patch(f"{_SESSION_MODULE}.pop_pending_create", return_value=None),
            patch(f"{_SESSION_MODULE}.get_pending_create_owner_for_thread",
                  return_value=None),
            patch(f"{_SESSION_MODULE}.get_pending_setup", return_value=None),
        ):
            er._handle_thread_message_inner(
                "C1", "T1", "U1", "iterate an idea for a chatbot", "E1",
            )

        mock_mem_reply.assert_not_called()
        mock_interpret.assert_called_once()

    def test_normal_text_consumed_as_memory(self):
        """Normal content text should still be consumed as memory."""
        import crewai_productfeature_planner.apis.slack.events_router as er
        from crewai_productfeature_planner.apis.slack.session_manager import (
            mark_pending_memory,
        )

        mark_pending_memory("U1", "C1", "T1", "knowledge", "proj-1")

        with (
            patch.object(er, "handle_memory_reply") as mock_mem_reply,
            patch.object(er, "_interpret_and_act") as mock_interpret,
            patch.object(er, "touch_thread"),
            patch(f"{_SESSION_MODULE}.pop_pending_create", return_value=None),
            patch(f"{_SESSION_MODULE}.get_pending_create_owner_for_thread",
                  return_value=None),
            patch(f"{_SESSION_MODULE}.get_pending_setup", return_value=None),
        ):
            er._handle_thread_message_inner(
                "C1", "T1", "U1", "https://docs.example.com/guide", "E1",
            )

        # Memory handler SHOULD be called
        mock_mem_reply.assert_called_once()
        # Intent classifier should NOT run
        mock_interpret.assert_not_called()

    def test_configure_memory_stays_in_memory_mode(self):
        """Typing 'configure memory' while in pending_memory should NOT
        cancel — it's still memory-related."""
        import crewai_productfeature_planner.apis.slack.events_router as er
        from crewai_productfeature_planner.apis.slack.session_manager import (
            mark_pending_memory,
        )

        mark_pending_memory("U1", "C1", "T1", "knowledge", "proj-1")

        with (
            patch.object(er, "handle_memory_reply") as mock_mem_reply,
            patch.object(er, "_interpret_and_act") as mock_interpret,
            patch.object(er, "touch_thread"),
            patch(f"{_SESSION_MODULE}.pop_pending_create", return_value=None),
            patch(f"{_SESSION_MODULE}.get_pending_create_owner_for_thread",
                  return_value=None),
            patch(f"{_SESSION_MODULE}.get_pending_setup", return_value=None),
        ):
            er._handle_thread_message_inner(
                "C1", "T1", "U1", "configure memory", "E1",
            )

        # configure_memory phrase matches, but intent is "configure_memory"
        # which is excluded from the cancel check — stays in memory mode
        mock_mem_reply.assert_called_once()
        mock_interpret.assert_not_called()
