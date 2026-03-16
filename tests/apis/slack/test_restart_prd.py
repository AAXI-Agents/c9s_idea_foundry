"""Tests for the restart_prd intent — phrase matching, handler, and confirmation flow."""

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


_EVENTS_MODULE = "crewai_productfeature_planner.apis.slack.events_router"
_TOOLS_MODULE = "crewai_productfeature_planner.tools.slack_tools"
_SESSION_MODULE = "crewai_productfeature_planner.apis.slack.session_manager"

_ACTIVE_SESSION = {
    "project_id": "proj-default",
    "project_name": "Default Project",
    "active": True,
}


# ---------------------------------------------------------------------------
# Phrase matching — _RESTART_PRD_PHRASES should match restart, not resume
# ---------------------------------------------------------------------------


class TestRestartPhraseMatching:
    """Verify _RESTART_PRD_PHRASES matches restart-related phrases."""

    def test_restart_prd_in_restart_phrases(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _RESTART_PRD_PHRASES,
        )
        assert "restart prd" in _RESTART_PRD_PHRASES
        assert "restart flow" in _RESTART_PRD_PHRASES
        assert "restart scan" in _RESTART_PRD_PHRASES
        assert "start over" in _RESTART_PRD_PHRASES
        assert "redo the prd" in _RESTART_PRD_PHRASES

    def test_restart_phrases_not_in_resume(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _RESUME_PRD_PHRASES,
        )
        assert "restart prd" not in _RESUME_PRD_PHRASES
        assert "restart prd flow" not in _RESUME_PRD_PHRASES
        assert "restart flow" not in _RESUME_PRD_PHRASES

    def test_resume_phrases_unchanged(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _RESUME_PRD_PHRASES,
        )
        assert "resume prd" in _RESUME_PRD_PHRASES
        assert "continue prd" in _RESUME_PRD_PHRASES
        assert "unpause" in _RESUME_PRD_PHRASES

    def test_phrase_fallback_restart(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _phrase_fallback,
        )
        result = _phrase_fallback("restart prd")
        assert result["intent"] == "restart_prd"

    def test_phrase_fallback_start_over(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _phrase_fallback,
        )
        result = _phrase_fallback("start over")
        assert result["intent"] == "restart_prd"

    def test_phrase_fallback_resume_still_works(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _phrase_fallback,
        )
        result = _phrase_fallback("resume prd")
        assert result["intent"] == "resume_prd"

    def test_phrase_fallback_restart_scan(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _phrase_fallback,
        )
        result = _phrase_fallback("restart scan of the idea")
        assert result["intent"] == "restart_prd"


# ---------------------------------------------------------------------------
# Intent routing — restart_prd should call _handle_restart_prd
# ---------------------------------------------------------------------------


class TestRestartIntentRouting:
    """Verify restart_prd intent routes to the restart handler."""

    @patch(f"{_SESSION_MODULE}.get_context_session", return_value=_ACTIVE_SESSION)
    @patch(f"{_TOOLS_MODULE}.SlackSendMessageTool")
    @patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool")
    @patch(f"{_EVENTS_MODULE}._handle_restart_prd")
    def test_restart_prd_phrase_routes_to_handler(
        self, mock_restart, mock_interpret, mock_send, mock_session,
    ):
        mock_interpret_inst = MagicMock()
        mock_interpret_inst.run.return_value = json.dumps({
            "intent": "restart_prd",
            "idea": None,
            "reply": "Restarting...",
        })
        mock_interpret.return_value = mock_interpret_inst
        mock_send.return_value = MagicMock()

        # Patch log_interaction to avoid DB calls
        with patch(
            "crewai_productfeature_planner.mongodb.agent_interactions"
            ".repository.log_interaction",
        ):
            er._interpret_and_act("C1", "T1", "U1", "restart prd", "E1")

        mock_restart.assert_called_once()

    @patch(f"{_SESSION_MODULE}.get_context_session", return_value=_ACTIVE_SESSION)
    @patch(f"{_TOOLS_MODULE}.SlackSendMessageTool")
    @patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool")
    @patch(f"{_EVENTS_MODULE}._handle_restart_prd")
    @patch(f"{_EVENTS_MODULE}._handle_resume_prd")
    def test_restart_does_not_route_to_resume(
        self, mock_resume, mock_restart, mock_interpret, mock_send, mock_session,
    ):
        """'restart prd' should NOT call the resume handler."""
        mock_interpret_inst = MagicMock()
        mock_interpret_inst.run.return_value = json.dumps({
            "intent": "restart_prd",
            "idea": None,
            "reply": "",
        })
        mock_interpret.return_value = mock_interpret_inst
        mock_send.return_value = MagicMock()

        with patch(
            "crewai_productfeature_planner.mongodb.agent_interactions"
            ".repository.log_interaction",
        ):
            er._interpret_and_act("C1", "T1", "U1", "restart prd", "E1")

        mock_restart.assert_called_once()
        mock_resume.assert_not_called()

    @patch(f"{_SESSION_MODULE}.get_context_session", return_value=_ACTIVE_SESSION)
    @patch(f"{_TOOLS_MODULE}.SlackSendMessageTool")
    @patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool")
    @patch(f"{_EVENTS_MODULE}._handle_resume_prd")
    def test_resume_still_routes_correctly(
        self, mock_resume, mock_interpret, mock_send, mock_session,
    ):
        """'resume prd' should still call the resume handler."""
        mock_interpret_inst = MagicMock()
        mock_interpret_inst.run.return_value = json.dumps({
            "intent": "resume_prd",
            "idea": None,
            "reply": "",
        })
        mock_interpret.return_value = mock_interpret_inst
        mock_send.return_value = MagicMock()

        with patch(
            "crewai_productfeature_planner.mongodb.agent_interactions"
            ".repository.log_interaction",
        ):
            er._interpret_and_act("C1", "T1", "U1", "resume prd", "E1")

        mock_resume.assert_called_once()


# ---------------------------------------------------------------------------
# handle_restart_prd — confirmation flow
# ---------------------------------------------------------------------------


class TestHandleRestartPrd:
    """Verify handle_restart_prd posts confirmation buttons."""

    @patch(
        "crewai_productfeature_planner.mongodb.find_unfinalized",
        return_value=[],
    )
    def test_no_active_run_posts_not_found(self, mock_find):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_restart_prd,
        )

        send_tool = MagicMock()
        handle_restart_prd("C1", "T1", "U1", send_tool, "E1")

        send_tool.run.assert_called_once()
        msg = send_tool.run.call_args[1]["text"]
        assert "No active PRD runs found" in msg

    @patch(
        "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.find_unfinalized",
        return_value=[
            {
                "run_id": "run-xyz",
                "idea": "Dark mode feature",
                "sections_done": 3,
                "total_sections": 12,
                "project_id": "proj-1",
            }
        ],
    )
    def test_active_run_posts_confirmation_buttons(self, mock_find, mock_client):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_restart_prd,
        )

        mock_slack = MagicMock()
        mock_client.return_value = mock_slack
        send_tool = MagicMock()

        handle_restart_prd("C1", "T1", "U1", send_tool, "E1")

        mock_slack.chat_postMessage.assert_called_once()
        call_kwargs = mock_slack.chat_postMessage.call_args[1]
        assert call_kwargs["channel"] == "C1"
        assert call_kwargs["thread_ts"] == "T1"

        blocks = call_kwargs["blocks"]
        assert len(blocks) == 2
        # First block is text describing the restart
        assert "Restart PRD Flow" in blocks[0]["text"]["text"]
        assert "run-xyz" in blocks[0]["text"]["text"]
        assert "Dark mode feature" in blocks[0]["text"]["text"]
        # Second block has buttons
        elements = blocks[1]["elements"]
        action_ids = [e["action_id"] for e in elements]
        assert "restart_prd_confirm" in action_ids
        assert "restart_prd_cancel" in action_ids

    @patch(
        "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.find_unfinalized",
        return_value=[
            {
                "run_id": "run-proj",
                "idea": "Right idea",
                "sections_done": 1,
                "total_sections": 12,
                "project_id": "proj-A",
            },
            {
                "run_id": "run-other",
                "idea": "Wrong idea",
                "sections_done": 5,
                "total_sections": 12,
                "project_id": "proj-B",
            },
        ],
    )
    def test_filters_by_project_id(self, mock_find, mock_client):
        """When project_id is provided, only runs for that project are shown."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_restart_prd,
        )

        mock_slack = MagicMock()
        mock_client.return_value = mock_slack
        send_tool = MagicMock()

        handle_restart_prd("C1", "T1", "U1", send_tool, "E1", project_id="proj-A")

        call_kwargs = mock_slack.chat_postMessage.call_args[1]
        blocks = call_kwargs["blocks"]
        # The confirmation should mention the run for proj-A
        assert "run-proj" in blocks[0]["text"]["text"]
        assert "Right idea" in blocks[0]["text"]["text"]

    @patch(
        "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.find_unfinalized",
        return_value=[
            {
                "run_id": "run-long",
                "idea": "A" * 3000,
                "sections_done": 2,
                "total_sections": 12,
                "project_id": "proj-1",
            }
        ],
    )
    def test_long_idea_truncated_in_confirmation(self, mock_find, mock_client):
        """Ideas longer than 500 chars should be truncated to stay within
        the Slack 3000-char section block limit."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_restart_prd,
        )

        mock_slack = MagicMock()
        mock_client.return_value = mock_slack
        send_tool = MagicMock()

        handle_restart_prd("C1", "T1", "U1", send_tool, "E1")

        call_kwargs = mock_slack.chat_postMessage.call_args[1]
        block_text = call_kwargs["blocks"][0]["text"]["text"]
        # The full 3000-char idea should NOT appear verbatim
        assert "A" * 3000 not in block_text
        # Must be under the Slack 3000-char limit
        assert len(block_text) <= 3000
        # Truncation marker should be present
        assert "…" in block_text


# ---------------------------------------------------------------------------
# execute_restart_prd — archive + kickoff
# ---------------------------------------------------------------------------


class TestExecuteRestartPrd:
    """Verify execute_restart_prd archives the old run and kicks off a new flow."""

    @patch(
        "crewai_productfeature_planner.apis.slack._flow_handlers.kick_off_prd_flow",
    )
    @patch(
        "crewai_productfeature_planner.tools.slack_tools.SlackSendMessageTool",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.crew_jobs.repository.update_job_status",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository.mark_archived",
        return_value=1,
    )
    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository.find_run_any_status",
        return_value={
            "run_id": "run-old",
            "idea": "AI Chatbot",
            "project_id": "proj-1",
        },
    )
    def test_archives_and_kicks_off(
        self, mock_find, mock_archive, mock_job_status, mock_send_cls, mock_kickoff,
    ):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            execute_restart_prd,
        )

        mock_send = MagicMock()
        mock_send_cls.return_value = mock_send

        execute_restart_prd(
            run_id="run-old",
            channel="C1",
            thread_ts="T1",
            user="U1",
        )

        # Old run should be archived
        mock_archive.assert_called_once_with("run-old")

        # Crew job should be archived too
        mock_job_status.assert_called_once_with("run-old", "archived")

        # Ack message should mention archiving and new flow
        mock_send.run.assert_called_once()
        msg = mock_send.run.call_args[1]["text"]
        assert "Archived run" in msg
        assert "run-old" in msg
        assert "AI Chatbot" in msg

        # New flow should be kicked off with same idea
        mock_kickoff.assert_called_once()
        kw = mock_kickoff.call_args[1]
        assert kw["idea"] == "AI Chatbot"
        assert kw["channel"] == "C1"

    @patch(
        "crewai_productfeature_planner.tools.slack_tools.SlackSendMessageTool",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository.find_run_any_status",
        return_value=None,
    )
    def test_run_not_found_posts_error(
        self, mock_find, mock_send_cls,
    ):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            execute_restart_prd,
        )

        mock_send = MagicMock()
        mock_send_cls.return_value = mock_send

        execute_restart_prd(
            run_id="run-gone",
            channel="C1",
            thread_ts="T1",
            user="U1",
        )

        mock_send.run.assert_called_once()
        msg = mock_send.run.call_args[1]["text"]
        assert "Could not find run" in msg

    @patch(
        "crewai_productfeature_planner.apis.slack._flow_handlers.kick_off_prd_flow",
    )
    @patch(
        "crewai_productfeature_planner.tools.slack_tools.SlackSendMessageTool",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.crew_jobs.repository.update_job_status",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository.mark_archived",
        return_value=1,
    )
    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository.find_run_any_status",
        return_value={
            "run_id": "run-fallback",
            "idea": "",
            "finalized_idea": "Fallback Chatbot Idea",
            "project_id": "proj-1",
        },
    )
    def test_falls_back_to_finalized_idea(
        self, mock_find, mock_archive, mock_job_status, mock_send_cls, mock_kickoff,
    ):
        """When the 'idea' field is empty, execute_restart_prd should fall
        back to finalized_idea instead of showing '(unknown idea)'."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            execute_restart_prd,
        )

        mock_send = MagicMock()
        mock_send_cls.return_value = mock_send

        execute_restart_prd(
            run_id="run-fallback",
            channel="C1",
            thread_ts="T1",
            user="U1",
        )

        # Message should contain the finalized idea, not "(unknown idea)"
        msg = mock_send.run.call_args[1]["text"]
        assert "Fallback Chatbot Idea" in msg
        assert "(unknown idea)" not in msg

        # New flow should use the finalized idea
        kw = mock_kickoff.call_args[1]
        assert kw["idea"] == "Fallback Chatbot Idea"


# ---------------------------------------------------------------------------
# interactions_router — restart button actions
# ---------------------------------------------------------------------------


class TestRestartPrdInteraction:
    """Verify _handle_restart_prd_action handles confirm and cancel."""

    @patch(
        "crewai_productfeature_planner.apis.slack._flow_handlers.execute_restart_prd",
    )
    @patch(
        "crewai_productfeature_planner.apis.slack.session_manager.get_context_session",
        return_value={"project_id": "proj-1"},
    )
    @patch(
        "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
    )
    def test_confirm_calls_execute(self, mock_client, mock_session, mock_execute):
        from crewai_productfeature_planner.apis.slack.interactions_router import (
            _handle_restart_prd_action,
        )

        _handle_restart_prd_action(
            "restart_prd_confirm", "run-abc", "U1", "C1", "T1",
        )

        mock_execute.assert_called_once_with(
            run_id="run-abc",
            channel="C1",
            thread_ts="T1",
            user="U1",
            project_id="proj-1",
        )

    @patch(
        "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
    )
    def test_cancel_posts_message(self, mock_client):
        from crewai_productfeature_planner.apis.slack.interactions_router import (
            _handle_restart_prd_action,
        )

        mock_slack = MagicMock()
        mock_client.return_value = mock_slack

        _handle_restart_prd_action(
            "restart_prd_cancel", "run-abc", "U1", "C1", "T1",
        )

        mock_slack.chat_postMessage.assert_called_once()
        msg = mock_slack.chat_postMessage.call_args[1]["text"]
        assert "cancelled" in msg.lower()


# ---------------------------------------------------------------------------
# extract_idea_number — number parsing from user text
# ---------------------------------------------------------------------------


class TestExtractIdeaNumber:
    """Verify extract_idea_number parses numbered idea references."""

    def test_idea_hash_1(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            extract_idea_number,
        )
        assert extract_idea_number("restart the iteration scan for idea #1") == 1

    def test_idea_hash_2(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            extract_idea_number,
        )
        assert extract_idea_number("resume idea #2") == 2

    def test_idea_no_hash(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            extract_idea_number,
        )
        assert extract_idea_number("restart idea 3") == 3

    def test_hash_only(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            extract_idea_number,
        )
        assert extract_idea_number("resume #5") == 5

    def test_no_number(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            extract_idea_number,
        )
        assert extract_idea_number("restart prd") is None

    def test_no_idea_prefix(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            extract_idea_number,
        )
        assert extract_idea_number("random text with 42 number") is None

    def test_case_insensitive(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            extract_idea_number,
        )
        assert extract_idea_number("Restart Idea #10") == 10


# ---------------------------------------------------------------------------
# _resolve_idea_by_number — idea lookup by number
# ---------------------------------------------------------------------------


class TestResolveIdeaByNumber:
    """Verify _resolve_idea_by_number selects the correct idea."""

    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository"
        ".find_ideas_by_project",
        return_value=[],
    )
    def test_no_ideas_posts_error(self, mock_find):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _resolve_idea_by_number,
        )

        send_tool = MagicMock()
        result = _resolve_idea_by_number(1, "proj-1", "C1", "T1", "U1", send_tool)

        assert result is None
        send_tool.run.assert_called_once()
        assert "No ideas found" in send_tool.run.call_args[1]["text"]

    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository"
        ".find_ideas_by_project",
        return_value=[
            {"run_id": "run-a", "idea": "First idea", "status": "paused",
             "sections_done": 3, "total_sections": 12},
            {"run_id": "run-b", "idea": "Second idea", "status": "paused",
             "sections_done": 5, "total_sections": 12},
        ],
    )
    def test_out_of_range_posts_error(self, mock_find):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _resolve_idea_by_number,
        )

        send_tool = MagicMock()
        result = _resolve_idea_by_number(5, "proj-1", "C1", "T1", "U1", send_tool)

        assert result is None
        send_tool.run.assert_called_once()
        assert "out of range" in send_tool.run.call_args[1]["text"]

    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository"
        ".find_ideas_by_project",
        return_value=[
            {"run_id": "run-a", "idea": "First idea", "status": "paused",
             "sections_done": 3, "total_sections": 12},
            {"run_id": "run-b", "idea": "Second idea", "status": "inprogress",
             "sections_done": 5, "total_sections": 12},
        ],
    )
    def test_selects_correct_idea(self, mock_find):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _resolve_idea_by_number,
        )

        send_tool = MagicMock()
        result = _resolve_idea_by_number(2, "proj-1", "C1", "T1", "U1", send_tool)

        assert result is not None
        assert result["run_id"] == "run-b"
        assert result["idea"] == "Second idea"
        send_tool.run.assert_not_called()

    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository"
        ".find_ideas_by_project",
        return_value=[
            {"run_id": "run-a", "idea": "Only idea", "status": "paused",
             "sections_done": 1, "total_sections": 12},
        ],
    )
    def test_zero_out_of_range(self, mock_find):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _resolve_idea_by_number,
        )

        send_tool = MagicMock()
        result = _resolve_idea_by_number(0, "proj-1", "C1", "T1", "U1", send_tool)

        assert result is None
        assert "out of range" in send_tool.run.call_args[1]["text"]


# ---------------------------------------------------------------------------
# Restart with idea number — uses _resolve_idea_by_number
# ---------------------------------------------------------------------------


class TestRestartWithIdeaNumber:
    """Verify handle_restart_prd respects idea_number parameter."""

    @patch(
        "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository"
        ".find_ideas_by_project",
        return_value=[
            {"run_id": "run-1", "idea": "Idea one", "status": "paused",
             "sections_done": 2, "total_sections": 12},
            {"run_id": "run-2", "idea": "Idea two", "status": "inprogress",
             "sections_done": 4, "total_sections": 12},
        ],
    )
    def test_restart_idea_number_selects_correct_run(self, mock_find, mock_client):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_restart_prd,
        )

        mock_slack = MagicMock()
        mock_client.return_value = mock_slack
        send_tool = MagicMock()

        handle_restart_prd(
            "C1", "T1", "U1", send_tool, "E1",
            project_id="proj-1", idea_number=2,
        )

        # Should post confirmation for "Idea two" (run-2), not run-1
        call_kwargs = mock_slack.chat_postMessage.call_args[1]
        blocks = call_kwargs["blocks"]
        assert "run-2" in blocks[0]["text"]["text"]
        assert "Idea two" in blocks[0]["text"]["text"]

    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository"
        ".find_ideas_by_project",
        return_value=[
            {"run_id": "run-x", "idea": "Only idea", "status": "paused",
             "sections_done": 1, "total_sections": 12},
        ],
    )
    def test_restart_idea_number_out_of_range(self, mock_find):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_restart_prd,
        )

        send_tool = MagicMock()
        handle_restart_prd(
            "C1", "T1", "U1", send_tool, "E1",
            project_id="proj-1", idea_number=5,
        )

        send_tool.run.assert_called_once()
        assert "out of range" in send_tool.run.call_args[1]["text"]


# ---------------------------------------------------------------------------
# Resume with idea number
# ---------------------------------------------------------------------------


class TestResumeWithIdeaNumber:
    """Verify handle_resume_prd respects idea_number parameter."""

    @patch(
        "crewai_productfeature_planner.apis.prd.service.resume_prd_flow",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository"
        ".save_slack_context",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository"
        ".find_ideas_by_project",
        return_value=[
            {"run_id": "run-a", "idea": "Alpha idea", "status": "paused",
             "sections_done": 1, "total_sections": 12},
            {"run_id": "run-b", "idea": "Beta idea", "status": "paused",
             "sections_done": 6, "total_sections": 12},
        ],
    )
    def test_resume_idea_number_selects_correct_run(
        self, mock_find, mock_save_ctx, mock_resume,
    ):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_resume_prd,
        )

        send_tool = MagicMock()

        # Prevent the background thread from actually running resume_prd_flow
        with patch("threading.Thread") as mock_thread:
            mock_thread.return_value = MagicMock()
            handle_resume_prd(
                "C1", "T1", "U1", send_tool,
                project_id="proj-1", idea_number=2,
            )

        # Ack message should reference "Beta idea" / "run-b"
        ack_text = send_tool.run.call_args[1]["text"]
        assert "run-b" in ack_text
        assert "Beta idea" in ack_text

    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository"
        ".find_ideas_by_project",
        return_value=[],
    )
    def test_resume_idea_number_no_ideas(self, mock_find):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_resume_prd,
        )

        send_tool = MagicMock()
        handle_resume_prd(
            "C1", "T1", "U1", send_tool,
            project_id="proj-1", idea_number=1,
        )

        send_tool.run.assert_called_once()
        assert "No ideas found" in send_tool.run.call_args[1]["text"]


# ---------------------------------------------------------------------------
# Phrase matching — new restart/resume patterns with idea numbers
# ---------------------------------------------------------------------------


class TestIdeaNumberPhraseRouting:
    """Verify phrases like 'restart idea #1' route correctly and extract number."""

    def test_restart_iteration_scan_phrase(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _phrase_fallback,
        )
        result = _phrase_fallback("restart the iteration scan for idea #1")
        assert result["intent"] == "restart_prd"

    def test_reiterate_from_start_phrase(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _phrase_fallback,
        )
        result = _phrase_fallback("reiterate from start idea #2")
        assert result["intent"] == "restart_prd"

    def test_rescan_idea_phrase(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _phrase_fallback,
        )
        result = _phrase_fallback("rescan idea #3")
        assert result["intent"] == "restart_prd"

    def test_resume_idea_phrase(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _phrase_fallback,
        )
        result = _phrase_fallback("resume idea #1")
        assert result["intent"] == "resume_prd"

    def test_continue_idea_phrase(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _phrase_fallback,
        )
        result = _phrase_fallback("continue idea #4")
        assert result["intent"] == "resume_prd"

    @patch(f"{_SESSION_MODULE}.get_context_session", return_value=_ACTIVE_SESSION)
    @patch(f"{_TOOLS_MODULE}.SlackSendMessageTool")
    @patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool")
    @patch(f"{_EVENTS_MODULE}._handle_restart_prd")
    def test_restart_idea_number_passed_to_handler(
        self, mock_restart, mock_interpret, mock_send, mock_session,
    ):
        """'restart the iteration scan for idea #1' should pass idea_number=1."""
        mock_interpret_inst = MagicMock()
        mock_interpret_inst.run.return_value = json.dumps({
            "intent": "unknown", "idea": None, "reply": "",
        })
        mock_interpret.return_value = mock_interpret_inst
        mock_send.return_value = MagicMock()

        with patch(
            "crewai_productfeature_planner.mongodb.agent_interactions"
            ".repository.log_interaction",
        ):
            er._interpret_and_act(
                "C1", "T1", "U1",
                "restart the iteration scan for idea #1", "E1",
            )

        mock_restart.assert_called_once()
        call_kwargs = mock_restart.call_args
        assert call_kwargs[1].get("idea_number") == 1 or \
            (len(call_kwargs[0]) > 6 and call_kwargs[0][6] == 1)

    @patch(f"{_SESSION_MODULE}.get_context_session", return_value=_ACTIVE_SESSION)
    @patch(f"{_TOOLS_MODULE}.SlackSendMessageTool")
    @patch(f"{_TOOLS_MODULE}.SlackInterpretMessageTool")
    @patch(f"{_EVENTS_MODULE}._handle_resume_prd")
    def test_resume_idea_number_passed_to_handler(
        self, mock_resume, mock_interpret, mock_send, mock_session,
    ):
        """'resume idea #2' should pass idea_number=2."""
        mock_interpret_inst = MagicMock()
        mock_interpret_inst.run.return_value = json.dumps({
            "intent": "unknown", "idea": None, "reply": "",
        })
        mock_interpret.return_value = mock_interpret_inst
        mock_send.return_value = MagicMock()

        with patch(
            "crewai_productfeature_planner.mongodb.agent_interactions"
            ".repository.log_interaction",
        ):
            er._interpret_and_act("C1", "T1", "U1", "resume idea #2", "E1")

        mock_resume.assert_called_once()
        call_kwargs = mock_resume.call_args
        assert call_kwargs[1].get("idea_number") == 2
