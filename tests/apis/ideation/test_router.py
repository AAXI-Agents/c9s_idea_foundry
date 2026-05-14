"""Tests for the Ideation Flow API router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app

_SERVICE = "crewai_productfeature_planner.apis.ideation.router"
_REPO = "crewai_productfeature_planner.mongodb.ideation_sessions.repository"
_SVC_MOD = "crewai_productfeature_planner.apis.ideation.service"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _make_session_doc(**overrides):
    doc = {
        "session_id": "abc123",
        "user_id": "user1",
        "project_id": None,
        "title": "Test Idea",
        "status": "active",
        "current_step": "a",
        "steps_data": {
            step: {"input": None, "output": None, "approved": False, "completed_at": None}
            for step in ["a", "b", "c", "d", "e"]
        },
        "messages": [],
        "created_at": "2026-05-01T00:00:00Z",
        "updated_at": "2026-05-01T00:00:00Z",
        "completed_at": None,
    }
    doc.update(overrides)
    return doc


def _make_message(**overrides):
    msg = {
        "id": "msg1",
        "role": "agent",
        "content": "Hello! Tell me about your idea.",
        "step": "a",
        "timestamp": "2026-05-01T00:00:01Z",
    }
    msg.update(overrides)
    return msg


# ── POST /flow/ideation/kickoff ──────────────────────────────


class TestKickoff:
    def test_successful_kickoff(self, client):
        session = _make_session_doc(project_id="proj1")
        with (
            patch(f"{_SERVICE}.get_project") as mock_proj,
            patch(f"{_SERVICE}.start_ideation_session", new_callable=AsyncMock) as mock_start,
        ):
            mock_proj.return_value = {"project_id": "proj1"}
            mock_start.return_value = session
            resp = client.post(
                "/flow/ideation/kickoff",
                json={"title": "Test Idea", "project_id": "proj1"},
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["session_id"] == "abc123"
        assert body["status"] == "active"
        assert body["current_step"] == "ideation"

    def test_kickoff_with_initial_idea(self, client):
        session = _make_session_doc(project_id="proj1")
        with (
            patch(f"{_SERVICE}.get_project") as mock_proj,
            patch(f"{_SERVICE}.start_ideation_session", new_callable=AsyncMock) as mock_start,
        ):
            mock_proj.return_value = {"project_id": "proj1"}
            mock_start.return_value = session
            resp = client.post(
                "/flow/ideation/kickoff",
                json={"title": "My App", "idea": "A fitness app for seniors", "project_id": "proj1"},
            )
        assert resp.status_code == 201
        mock_start.assert_called_once()
        call_kwargs = mock_start.call_args[1]
        assert call_kwargs["initial_idea"] == "A fitness app for seniors"

    def test_kickoff_failure(self, client):
        with (
            patch(f"{_SERVICE}.get_project") as mock_proj,
            patch(f"{_SERVICE}.start_ideation_session", new_callable=AsyncMock) as mock_start,
        ):
            mock_proj.return_value = {"project_id": "proj1"}
            mock_start.return_value = None
            resp = client.post(
                "/flow/ideation/kickoff",
                json={"title": "Fail", "project_id": "proj1"},
            )
        assert resp.status_code == 500

    def test_kickoff_missing_project_id_returns_422(self, client):
        """project_id is required — omitting it returns 422."""
        resp = client.post(
            "/flow/ideation/kickoff",
            json={"title": "No project"},
        )
        assert resp.status_code == 422

    def test_kickoff_empty_project_id_returns_422(self, client):
        """project_id must be non-empty."""
        resp = client.post(
            "/flow/ideation/kickoff",
            json={"title": "Empty project", "project_id": ""},
        )
        assert resp.status_code == 422

    def test_kickoff_nonexistent_project_returns_404(self, client):
        """project_id referencing a non-existent project returns 404."""
        with patch(f"{_SERVICE}.get_project") as mock_proj:
            mock_proj.return_value = None
            resp = client.post(
                "/flow/ideation/kickoff",
                json={"title": "Bad project", "project_id": "nonexistent"},
            )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]


# ── GET /flow/ideation/sessions ──────────────────────────────


class TestListSessions:
    def test_list_sessions(self, client):
        sessions = [_make_session_doc(session_id=f"s{i}") for i in range(3)]
        with (
            patch(f"{_SERVICE}.count_sessions") as mock_count,
            patch(f"{_SERVICE}.list_sessions_paginated") as mock_list,
        ):
            mock_count.return_value = 3
            mock_list.return_value = sessions
            resp = client.get("/flow/ideation/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3
        assert body["page"] == 1

    def test_list_with_status_filter(self, client):
        with (
            patch(f"{_SERVICE}.count_sessions") as mock_count,
            patch(f"{_SERVICE}.list_sessions_paginated") as mock_list,
        ):
            mock_count.return_value = 0
            mock_list.return_value = []
            resp = client.get("/flow/ideation/sessions?status=completed")
        assert resp.status_code == 200
        mock_count.assert_called_once()
        call_kwargs = mock_count.call_args[1]
        assert call_kwargs["status"] == "completed"


# ── GET /flow/ideation/sessions/{id} ─────────────────────────


class TestGetSession:
    def test_get_existing_session(self, client):
        session = _make_session_doc()
        with patch(f"{_SERVICE}.get_session") as mock_get:
            mock_get.return_value = session
            resp = client.get("/flow/ideation/sessions/abc123")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "abc123"
        assert body["current_step"] == "ideation"
        assert "outputs" in body

    def test_get_nonexistent_session(self, client):
        with patch(f"{_SERVICE}.get_session") as mock_get:
            mock_get.return_value = None
            resp = client.get("/flow/ideation/sessions/nonexistent")
        assert resp.status_code == 404


# ── GET /flow/ideation/sessions/{id}/messages ─────────────────


class TestGetMessages:
    def test_get_messages(self, client):
        msgs = [_make_message(id=f"m{i}") for i in range(3)]
        with (
            patch(f"{_SERVICE}.get_session") as mock_get_session,
            patch(f"{_SERVICE}.get_messages") as mock_msgs,
        ):
            mock_get_session.return_value = _make_session_doc()
            mock_msgs.return_value = msgs
            resp = client.get("/flow/ideation/sessions/abc123/messages")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["messages"]) == 3
        assert body["has_more"] is False

    def test_get_messages_with_step_filter(self, client):
        with (
            patch(f"{_SERVICE}.get_session") as mock_get_session,
            patch(f"{_SERVICE}.get_messages") as mock_msgs,
        ):
            mock_get_session.return_value = _make_session_doc()
            mock_msgs.return_value = []
            resp = client.get("/flow/ideation/sessions/abc123/messages?step=persona")
        assert resp.status_code == 200
        mock_msgs.assert_called_once()
        call_kwargs = mock_msgs.call_args[1]
        # Router converts frontend name "persona" → internal "b"
        assert call_kwargs["step"] == "b"

    def test_get_messages_session_not_found(self, client):
        with patch(f"{_SERVICE}.get_session") as mock_get_session:
            mock_get_session.return_value = None
            resp = client.get("/flow/ideation/sessions/nope/messages")
        assert resp.status_code == 404


# ── POST /flow/ideation/sessions/{id}/respond ─────────────────


class TestRespond:
    def test_respond_success(self, client):
        agent_msg = {
            "id": "msg2",
            "role": "agent",
            "content": "Great idea!",
            "step": "a",
            "timestamp": "2026-05-01T00:00:02Z",
        }
        with (
            patch(f"{_SERVICE}.get_session") as mock_get,
            patch(f"{_SERVICE}.handle_user_response", new_callable=AsyncMock) as mock_respond,
        ):
            mock_get.return_value = _make_session_doc()
            mock_respond.return_value = agent_msg
            resp = client.post(
                "/flow/ideation/sessions/abc123/respond",
                json={"content": "A fitness app for dogs"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["message_id"] == "msg2"
        assert body["status"] == "completed"
        assert body["content"] == "Great idea!"
        assert body["step"] == "a"
        assert body["role"] == "agent"

    def test_respond_inactive_session(self, client):
        with patch(f"{_SERVICE}.get_session") as mock_get:
            mock_get.return_value = _make_session_doc(status="completed")
            resp = client.post(
                "/flow/ideation/sessions/abc123/respond",
                json={"content": "test"},
            )
        assert resp.status_code == 409

    def test_respond_empty_content(self, client):
        resp = client.post(
            "/flow/ideation/sessions/abc123/respond",
            json={"content": ""},
        )
        assert resp.status_code == 422

    def test_respond_with_structured_output(self, client):
        """Agent returns structured questions → metadata included in response."""
        agent_msg = {
            "id": "msg3",
            "role": "agent",
            "content": "Great idea! Let me dig deeper.",
            "step": "a",
            "metadata": {
                "render_type": "structured_questions",
                "structured": {
                    "acknowledgment": "Great idea! Let me dig deeper.",
                    "questions": [
                        {
                            "id": 1,
                            "question": "Who is the audience?",
                            "context": "Audience shapes everything.",
                            "recommendations": [
                                {"label": "SMBs", "pro": "Large market", "con": "Price sensitive", "complexity": "Low"},
                                {"label": "Enterprise", "pro": "High ACV", "con": "Long sales cycle", "complexity": "High"},
                                {"label": "Prosumers", "pro": "Quick adoption", "con": "Low willingness to pay", "complexity": "Medium"},
                            ],
                        },
                    ] * 3,
                    "agent_insight": "Strong timing.",
                    "summary_draft": None,
                },
            },
        }
        with (
            patch(f"{_SERVICE}.get_session") as mock_get,
            patch(f"{_SERVICE}.handle_user_response", new_callable=AsyncMock) as mock_respond,
        ):
            mock_get.return_value = _make_session_doc()
            mock_respond.return_value = agent_msg
            resp = client.post(
                "/flow/ideation/sessions/abc123/respond",
                json={"content": "A fitness app for dogs"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["metadata"]["render_type"] == "structured_questions"
        assert len(body["metadata"]["structured"]["questions"]) == 3

    def test_respond_with_selection(self, client):
        """User submits structured answers → passed to service."""
        agent_msg = {
            "id": "msg4",
            "role": "agent",
            "content": "Thanks for your selections!",
            "step": "a",
            "metadata": None,
        }
        with (
            patch(f"{_SERVICE}.get_session") as mock_get,
            patch(f"{_SERVICE}.handle_user_response", new_callable=AsyncMock) as mock_respond,
        ):
            mock_get.return_value = _make_session_doc()
            mock_respond.return_value = agent_msg
            resp = client.post(
                "/flow/ideation/sessions/abc123/respond",
                json={
                    "content": "My selections",
                    "response_type": "selection",
                    "metadata": {
                        "answers": [
                            {"question_id": 1, "selected_option": 0},
                            {"question_id": 2, "custom_feedback": "Both B2B and B2C"},
                        ]
                    },
                },
            )
        assert resp.status_code == 200
        # Verify service received response_type and metadata
        call_kwargs = mock_respond.call_args[1]
        assert call_kwargs["response_type"] == "selection"
        assert len(call_kwargs["metadata"]["answers"]) == 2


# ── POST /flow/ideation/sessions/{id}/advance ─────────────────


class TestAdvance:
    def test_advance_success(self, client):
        with (
            patch(f"{_SERVICE}.get_session") as mock_get,
            patch(f"{_SERVICE}.handle_advance", new_callable=AsyncMock) as mock_advance,
        ):
            mock_get.return_value = _make_session_doc()
            mock_advance.return_value = {
                "previous_step": "a",
                "new_step": "b",
                "completed": False,
            }
            resp = client.post("/flow/ideation/sessions/abc123/advance")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "advanced"
        assert body["previous_step"] == "ideation"
        assert body["current_step"] == "persona"

    def test_advance_completes_session(self, client):
        with (
            patch(f"{_SERVICE}.get_session") as mock_get,
            patch(f"{_SERVICE}.handle_advance", new_callable=AsyncMock) as mock_advance,
        ):
            mock_get.return_value = _make_session_doc(current_step="e")
            mock_advance.return_value = {
                "previous_step": "e",
                "new_step": None,
                "completed": True,
                "prd_run_id": "run123",
            }
            resp = client.post("/flow/ideation/sessions/abc123/advance")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["prd_run_id"] == "run123"

    def test_advance_inactive_session(self, client):
        with patch(f"{_SERVICE}.get_session") as mock_get:
            mock_get.return_value = _make_session_doc(status="abandoned")
            resp = client.post("/flow/ideation/sessions/abc123/advance")
        assert resp.status_code == 409


# ── POST /flow/ideation/sessions/{id}/rollback ────────────────


class TestRollback:
    def test_rollback_success(self, client):
        with (
            patch(f"{_SERVICE}.get_session") as mock_get,
            patch(f"{_SERVICE}.handle_rollback", new_callable=AsyncMock) as mock_roll,
        ):
            mock_get.return_value = _make_session_doc(current_step="b")
            mock_roll.return_value = {
                "previous_step": "b",
                "new_step": "a",
            }
            resp = client.post("/flow/ideation/sessions/abc123/rollback")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "rolled_back"
        assert body["current_step"] == "ideation"

    def test_rollback_at_first_step(self, client):
        with (
            patch(f"{_SERVICE}.get_session") as mock_get,
            patch(f"{_SERVICE}.handle_rollback", new_callable=AsyncMock) as mock_roll,
        ):
            mock_get.return_value = _make_session_doc(current_step="a")
            mock_roll.return_value = {"error": "Already at first step — cannot roll back."}
            resp = client.post("/flow/ideation/sessions/abc123/rollback")
        assert resp.status_code == 400

    def test_rollback_session_not_found(self, client):
        with patch(f"{_SERVICE}.get_session") as mock_get:
            mock_get.return_value = None
            resp = client.post("/flow/ideation/sessions/nonexistent/rollback")
        assert resp.status_code == 404
