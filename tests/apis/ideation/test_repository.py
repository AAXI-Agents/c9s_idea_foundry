"""Tests for the ideationSessions MongoDB repository."""

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.mongodb.ideation_sessions.repository import (
    IDEATION_SESSIONS_COLLECTION,
    STEP_ORDER,
    advance_step,
    append_message,
    complete_session,
    create_session,
    get_messages,
    get_session,
    list_sessions,
    rollback_step,
    save_step_data,
    update_session_status,
)

_REPO = "crewai_productfeature_planner.mongodb.ideation_sessions.repository"


def _mock_col(mock_db):
    """Get the mock collection from a mock db."""
    return mock_db.__getitem__.return_value


def _make_session_doc(**overrides):
    doc = {
        "session_id": "sess1",
        "user_id": "user1",
        "project_id": None,
        "title": "Test",
        "status": "active",
        "current_step": "a",
        "steps_data": {
            s: {"input": None, "output": None, "approved": False, "completed_at": None}
            for s in STEP_ORDER
        },
        "messages": [],
        "created_at": "2026-05-01T00:00:00Z",
        "updated_at": "2026-05-01T00:00:00Z",
        "completed_at": None,
    }
    doc.update(overrides)
    return doc


class TestCreateSession:
    def test_creates_and_returns_doc(self):
        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.insert_one.return_value = MagicMock(acknowledged=True)

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            result = create_session(user_id="u1", title="My Idea")

        assert result is not None
        assert result["user_id"] == "u1"
        assert result["title"] == "My Idea"
        assert result["status"] == "active"
        assert result["current_step"] == "a"
        assert "session_id" in result
        col.insert_one.assert_called_once()

    def test_returns_none_on_failure(self):
        from pymongo.errors import PyMongoError

        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.insert_one.side_effect = PyMongoError("conn error")

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            result = create_session(user_id="u1")

        assert result is None


class TestAppendMessage:
    def test_appends_and_returns_id(self):
        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.update_one.return_value = MagicMock(modified_count=1)

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            msg_id = append_message(
                session_id="sess1",
                role="user",
                content="Hello",
                step="a",
            )

        assert msg_id is not None
        col.update_one.assert_called_once()

    def test_returns_none_when_session_not_found(self):
        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.update_one.return_value = MagicMock(modified_count=0)

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            msg_id = append_message(
                session_id="nope",
                role="user",
                content="Hello",
                step="a",
            )

        assert msg_id is None


class TestSaveStepData:
    def test_saves_input_and_output(self):
        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.update_one.return_value = MagicMock(modified_count=1)

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            ok = save_step_data(
                session_id="sess1",
                step="a",
                input_data="user text",
                output_data="agent text",
                approved=True,
            )

        assert ok is True
        call_args = col.update_one.call_args
        update_doc = call_args[0][1]["$set"]
        assert "steps_data.a.input" in update_doc
        assert "steps_data.a.output" in update_doc
        assert update_doc["steps_data.a.approved"] is True


class TestAdvanceStep:
    def test_advances_from_a_to_b(self):
        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.find_one.return_value = _make_session_doc(current_step="a")
        col.update_one.return_value = MagicMock(modified_count=1)

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            new_step = advance_step(session_id="sess1")

        assert new_step == "b"

    def test_completes_at_last_step(self):
        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.find_one.return_value = _make_session_doc(current_step="e")
        col.update_one.return_value = MagicMock(modified_count=1)

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            new_step = advance_step(session_id="sess1")

        assert new_step is None


class TestRollbackStep:
    def test_rolls_back_from_b_to_a(self):
        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.find_one.return_value = _make_session_doc(current_step="b")
        col.update_one.return_value = MagicMock(modified_count=1)

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            prev_step = rollback_step(session_id="sess1")

        assert prev_step == "a"

    def test_cannot_rollback_at_first_step(self):
        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.find_one.return_value = _make_session_doc(current_step="a")

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            result = rollback_step(session_id="sess1")

        assert result is None


class TestGetSession:
    def test_returns_session(self):
        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.find_one.return_value = _make_session_doc()

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            session = get_session(session_id="sess1")

        assert session is not None
        assert session["session_id"] == "sess1"

    def test_returns_none_when_not_found(self):
        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.find_one.return_value = None

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            session = get_session(session_id="nope")

        assert session is None


class TestListSessions:
    def test_lists_sessions(self):
        mock_db = MagicMock()
        col = _mock_col(mock_db)
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.skip.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.__iter__ = MagicMock(
            return_value=iter([_make_session_doc(session_id=f"s{i}") for i in range(2)])
        )
        col.find.return_value = cursor

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            sessions = list_sessions(user_id="user1")

        assert len(sessions) == 2


class TestGetMessages:
    def test_returns_all_messages(self):
        msgs = [
            {"id": "m1", "role": "agent", "content": "Hi", "step": "a", "timestamp": "t1"},
            {"id": "m2", "role": "user", "content": "Hello", "step": "a", "timestamp": "t2"},
        ]
        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.find_one.return_value = _make_session_doc(messages=msgs)

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            result = get_messages(session_id="sess1")

        assert len(result) == 2

    def test_filters_by_step(self):
        msgs = [
            {"id": "m1", "role": "agent", "content": "Hi", "step": "a", "timestamp": "t1"},
            {"id": "m2", "role": "agent", "content": "Next", "step": "b", "timestamp": "t2"},
        ]
        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.find_one.return_value = _make_session_doc(messages=msgs)

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            result = get_messages(session_id="sess1", step="b")

        assert len(result) == 1
        assert result[0]["step"] == "b"


class TestCompleteSession:
    def test_marks_completed(self):
        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.update_one.return_value = MagicMock(modified_count=1)

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            ok = complete_session(session_id="sess1")

        assert ok is True
        call_args = col.update_one.call_args
        update_doc = call_args[0][1]["$set"]
        assert update_doc["status"] == "completed"
        assert "completed_at" in update_doc
