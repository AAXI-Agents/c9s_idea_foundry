"""Tests for thread-based flow routing and flow summary (v0.37.1).

Issue #1: Thread messages silently dropped when in-memory cache expired
           but a flow document exists in MongoDB for that thread.
Issue #2: "Give me a summary of the refined idea" classified as
           general_question and replied with generic help instead of
           flow status summary.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from crewai_productfeature_planner.apis import app

_ER = "crewai_productfeature_planner.apis.slack.events_router"
_MH = "crewai_productfeature_planner.apis.slack._message_handler"
_WI_REPO = "crewai_productfeature_planner.mongodb.working_ideas.repository"
_WI_Q = "crewai_productfeature_planner.mongodb.working_ideas._queries"
_AI = "crewai_productfeature_planner.mongodb.agent_interactions"
_SM = "crewai_productfeature_planner.apis.slack.session_manager"
_ST = "crewai_productfeature_planner.tools.slack_tools"
_AI_REPO = "crewai_productfeature_planner.mongodb.agent_interactions.repository"


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    """Reset module-level caches between tests."""
    monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("SLACK_VERIFICATION_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_BYPASS", raising=False)

    import crewai_productfeature_planner.apis.slack.events_router as er

    with er._thread_lock:
        er._thread_conversations.clear()
        er._thread_last_active.clear()
    with er._seen_events_lock:
        er._seen_events.clear()
    er._bot_user_id = None


async def _post(payload: dict):
    body = json.dumps(payload).encode()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        return await ac.post(
            "/slack/events",
            content=body,
            headers={"Content-Type": "application/json"},
        )


def _event_payload(event: dict, event_id: str = "Ev_TEST") -> dict:
    return {"type": "event_callback", "event_id": event_id, "event": event}


# ======================================================================
# Issue #1: Flow thread recovery — thread messages should process
# when a working-idea document exists for the thread, even without
# in-memory cache or @mention.
# ======================================================================


class TestFlowThreadRecovery:
    """Thread messages with a MongoDB flow document should be processed."""

    @pytest.mark.anyio
    async def test_thread_message_processed_when_flow_doc_exists(self):
        """Message in a flow thread is processed when MongoDB has the doc."""
        handler = MagicMock()

        # Ensure bot_id is set so @mention checks can work
        import crewai_productfeature_planner.apis.slack.events_router as er
        er._bot_user_id = "B_BOT"

        with patch(f"{_ER}._handle_thread_message", handler), \
             patch(f"{_ER}.has_thread_conversation", return_value=False), \
             patch(
                 f"{_AI}.has_bot_thread_history",
                 return_value=False,
             ), \
             patch(
                 f"{_WI_REPO}.find_idea_by_thread",
                 return_value={"run_id": "R1", "status": "inprogress"},
             ), \
             patch(f"{_ER}.touch_thread"):
            resp = await _post(_event_payload({
                "type": "message",
                "subtype": "",
                "channel": "C_FLOW",
                "user": "U_USER",
                "text": "Give me a summary of the refined idea",
                "thread_ts": "1234.5678",
                "ts": "9999.0001",
            }))

        assert resp.status_code == 200
        handler.assert_called_once()

    @pytest.mark.anyio
    async def test_thread_message_still_ignored_when_no_flow_doc(self):
        """No flow doc → message remains silently dropped."""
        handler = MagicMock()

        import crewai_productfeature_planner.apis.slack.events_router as er
        er._bot_user_id = "B_BOT"

        with patch(f"{_ER}._handle_thread_message", handler), \
             patch(f"{_ER}.has_thread_conversation", return_value=False), \
             patch(
                 f"{_AI}.has_bot_thread_history",
                 return_value=False,
             ), \
             patch(
                 f"{_WI_REPO}.find_idea_by_thread",
                 return_value=None,
             ):
            resp = await _post(_event_payload({
                "type": "message",
                "subtype": "",
                "channel": "C_OTHER",
                "user": "U_USER",
                "text": "Hello bot",
                "thread_ts": "5555.0000",
                "ts": "9999.0002",
            }))

        assert resp.status_code == 200
        handler.assert_not_called()

    @pytest.mark.anyio
    async def test_thread_cache_reregistered_on_flow_hit(self):
        """After flow doc match, touch_thread is called for caching."""
        import crewai_productfeature_planner.apis.slack.events_router as er
        er._bot_user_id = "B_BOT"

        touch_mock = MagicMock()

        with patch(f"{_ER}._handle_thread_message", MagicMock()), \
             patch(f"{_ER}.has_thread_conversation", return_value=False), \
             patch(
                 f"{_AI}.has_bot_thread_history",
                 return_value=False,
             ), \
             patch(
                 f"{_WI_REPO}.find_idea_by_thread",
                 return_value={"run_id": "R1", "status": "completed"},
             ), \
             patch(f"{_ER}.touch_thread", touch_mock):
            await _post(_event_payload({
                "type": "message",
                "subtype": "",
                "channel": "C_FLOW",
                "user": "U_USER",
                "text": "status update?",
                "thread_ts": "1234.5678",
                "ts": "9999.0003",
            }))

        touch_mock.assert_called_with("C_FLOW", "1234.5678")

    @pytest.mark.anyio
    async def test_flow_thread_reason_logged(self):
        """The log reason includes 'flow_thread'."""
        import crewai_productfeature_planner.apis.slack.events_router as er
        er._bot_user_id = "B_BOT"

        with patch(f"{_ER}._handle_thread_message", MagicMock()), \
             patch(f"{_ER}.has_thread_conversation", return_value=False), \
             patch(
                 f"{_AI}.has_bot_thread_history",
                 return_value=False,
             ), \
             patch(
                 f"{_WI_REPO}.find_idea_by_thread",
                 return_value={"run_id": "R1", "status": "inprogress"},
             ), \
             patch(f"{_ER}.touch_thread", MagicMock()), \
             patch(f"{_ER}.logger") as mock_logger:
            await _post(_event_payload({
                "type": "message",
                "subtype": "",
                "channel": "C_FLOW",
                "user": "U_USER",
                "text": "anything",
                "thread_ts": "1234.5678",
                "ts": "9999.0004",
            }))

        # The "Thread follow-up..." info log should include "flow_thread"
        info_calls = [
            str(c) for c in mock_logger.info.call_args_list
            if "Thread follow-up" in str(c)
        ]
        assert any("flow_thread" in c for c in info_calls)


# ======================================================================
# Issue #2: Flow summary — "Give me a summary" in a flow thread should
# return a flow status instead of a generic help response.
# ======================================================================


class TestIsFlowSummaryRequest:
    """Unit tests for _is_summary_request phrase detection."""

    def test_summary_phrases_detected(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _is_summary_request,
        )

        assert _is_summary_request("Give me a summary of the refined idea") is True
        assert _is_summary_request("What's the current status?") is True
        assert _is_summary_request("How far along are we?") is True
        assert _is_summary_request("progress update please") is True
        assert _is_summary_request("Where are we with the PRD?") is True
        assert _is_summary_request("what section are you on?") is True

    def test_non_summary_phrases_not_detected(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _is_summary_request,
        )

        assert _is_summary_request("Create a new idea for me") is False
        assert _is_summary_request("What is a PRD?") is False
        assert _is_summary_request("How long does this take?") is False
        assert _is_summary_request("help") is False


class TestBuildFlowSummary:
    """Unit tests for _build_flow_summary."""

    def test_inprogress_with_sections(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _build_flow_summary,
        )

        doc = {
            "status": "inprogress",
            "idea": "Build an AI chatbot",
            "executive_summary": [{"iteration": 1, "content": "..."}],
            "section": {
                "executive_product_summary": [{"iteration": 1}],
                "engineering_plan": [{"iteration": 1}],
            },
        }
        summary = _build_flow_summary(doc)
        assert summary is not None
        assert ":gear: *In Progress*" in summary
        assert "3/12 sections complete" in summary
        assert "AI chatbot" in summary
        assert "Executive Summary" in summary
        assert "Remaining:" in summary

    def test_completed_flow(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _build_flow_summary,
        )

        doc = {
            "status": "completed",
            "idea": "Payment gateway",
            "executive_summary": [{"iteration": 1}],
            "section": {},
        }
        summary = _build_flow_summary(doc)
        assert ":white_check_mark: *Completed*" in summary

    def test_paused_flow(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _build_flow_summary,
        )

        doc = {
            "status": "paused",
            "idea": "Dashboard feature",
            "executive_summary": [],
            "section": {},
        }
        summary = _build_flow_summary(doc)
        assert ":pause_button: *Paused*" in summary
        assert "0/12 sections complete" in summary

    def test_long_idea_truncated(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _build_flow_summary,
        )

        doc = {
            "status": "inprogress",
            "idea": "X" * 300,
            "executive_summary": [],
            "section": {},
        }
        summary = _build_flow_summary(doc)
        assert "…" in summary


class TestSummaryIntegration:
    """Integration: general_question + summary phrase + flow doc → flow summary."""

    def test_summary_request_returns_flow_summary(self):
        """When general_question + summary phrase + flow doc → flow summary."""
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _interpret_and_act_inner,
        )

        mock_client = MagicMock()
        flow_doc = {
            "run_id": "R_FLOW",
            "status": "inprogress",
            "idea": "Build an AI chatbot for customer support",
            "executive_summary": [{"iteration": 1, "content": "exec..."}],
            "section": {
                "executive_product_summary": [{"iteration": 1}],
            },
        }

        with patch(
            f"{_ST}.SlackInterpretMessageTool"
        ) as MockInterp, patch(
            f"{_ST}.SlackSendMessageTool"
        ), patch(
            f"{_MH}.get_thread_history", return_value=[]
        ), patch(
            f"{_MH}.append_to_thread"
        ), patch(
            f"{_SM}.get_context_session",
            return_value={"project_id": "P1", "project_name": "Test Project"},
        ), patch(
            f"{_WI_REPO}.find_idea_by_thread", return_value=flow_doc
        ), patch(
            f"{_ST}._get_slack_client", return_value=mock_client
        ), patch(
            f"{_AI_REPO}.log_interaction"
        ):
            MockInterp.return_value.run.return_value = json.dumps({
                "intent": "general_question",
                "idea": None,
                "reply": "Here is some generic info about PRDs...",
            })

            _interpret_and_act_inner(
                channel="C_FLOW",
                thread_ts="1234.5678",
                user="U_USER",
                clean_text="Give me a summary of the refined idea",
                event_ts="9999.0001",
            )

        # Should post a flow summary, not the generic reply
        mock_client.chat_postMessage.assert_called_once()
        posted_text = mock_client.chat_postMessage.call_args[1]["text"]
        assert "In Progress" in posted_text
        assert "AI chatbot" in posted_text
        assert "2/12" in posted_text

    def test_non_summary_general_question_unchanged(self):
        """When general_question + NOT summary phrase → normal generic reply."""
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _interpret_and_act_inner,
        )

        mock_client = MagicMock()

        with patch(
            f"{_ST}.SlackInterpretMessageTool"
        ) as MockInterp, patch(
            f"{_ST}.SlackSendMessageTool"
        ), patch(
            f"{_MH}.get_thread_history", return_value=[]
        ), patch(
            f"{_MH}.append_to_thread"
        ), patch(
            f"{_SM}.get_context_session",
            return_value={"project_id": "P1", "project_name": "Test Project"},
        ), patch(
            f"{_ST}._get_slack_client", return_value=mock_client
        ), patch(
            f"{_AI_REPO}.log_interaction"
        ):
            MockInterp.return_value.run.return_value = json.dumps({
                "intent": "general_question",
                "idea": None,
                "reply": "A PRD is a document that defines product requirements...",
            })

            _interpret_and_act_inner(
                channel="C_FLOW",
                thread_ts="1234.5678",
                user="U_USER",
                clean_text="What is a PRD?",
                event_ts="9999.0002",
            )

        # Should post the generic reply (not a summary)
        mock_client.chat_postMessage.assert_called_once()
        posted_text = mock_client.chat_postMessage.call_args[1]["text"]
        assert "PRD" in posted_text
        # Should NOT contain flow summary markers
        assert "sections complete" not in posted_text

    def test_summary_request_no_flow_doc_falls_through(self):
        """When summary phrase but no flow doc → normal generic reply."""
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _interpret_and_act_inner,
        )

        mock_client = MagicMock()

        with patch(
            f"{_ST}.SlackInterpretMessageTool"
        ) as MockInterp, patch(
            f"{_ST}.SlackSendMessageTool"
        ), patch(
            f"{_MH}.get_thread_history", return_value=[]
        ), patch(
            f"{_MH}.append_to_thread"
        ), patch(
            f"{_SM}.get_context_session",
            return_value={"project_id": "P1", "project_name": "Test Project"},
        ), patch(
            f"{_WI_REPO}.find_idea_by_thread", return_value=None
        ), patch(
            f"{_ST}._get_slack_client", return_value=mock_client
        ), patch(
            f"{_AI_REPO}.log_interaction"
        ):
            MockInterp.return_value.run.return_value = json.dumps({
                "intent": "general_question",
                "idea": None,
                "reply": "I'm not sure what you're asking about...",
            })

            _interpret_and_act_inner(
                channel="C_FLOW",
                thread_ts="1234.5678",
                user="U_USER",
                clean_text="Give me the status please",
                event_ts="9999.0003",
            )

        # Should post generic reply since no flow doc
        mock_client.chat_postMessage.assert_called_once()
        posted_text = mock_client.chat_postMessage.call_args[1]["text"]
        assert "sections complete" not in posted_text


# ======================================================================
# find_idea_by_thread query tests
# ======================================================================


class TestFindIdeaByThread:
    """Unit tests for the MongoDB query function."""

    def test_returns_doc_when_found(self):
        from crewai_productfeature_planner.mongodb.working_ideas._queries import (
            find_idea_by_thread,
        )

        mock_doc = {
            "run_id": "R1",
            "idea": "test idea",
            "status": "inprogress",
            "slack_channel": "C1",
            "slack_thread_ts": "1234.0",
        }
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = mock_doc
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas._common.get_db",
            return_value=mock_db,
        ):
            result = find_idea_by_thread("C1", "1234.0")

        assert result is not None
        assert result["run_id"] == "R1"
        mock_collection.find_one.assert_called_once()
        query = mock_collection.find_one.call_args[0][0]
        assert query["slack_channel"] == "C1"
        assert query["slack_thread_ts"] == "1234.0"
        assert query["status"] == {"$ne": "archived"}

    def test_returns_none_when_not_found(self):
        from crewai_productfeature_planner.mongodb.working_ideas._queries import (
            find_idea_by_thread,
        )

        mock_collection = MagicMock()
        mock_collection.find_one.return_value = None
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas._common.get_db",
            return_value=mock_db,
        ):
            result = find_idea_by_thread("C1", "1234.0")

        assert result is None

    def test_returns_none_on_error(self):
        from pymongo.errors import PyMongoError

        from crewai_productfeature_planner.mongodb.working_ideas._queries import (
            find_idea_by_thread,
        )

        mock_collection = MagicMock()
        mock_collection.find_one.side_effect = PyMongoError("connection lost")
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas._common.get_db",
            return_value=mock_db,
        ):
            result = find_idea_by_thread("C1", "1234.0")

        assert result is None
