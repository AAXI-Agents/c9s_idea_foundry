"""Tests for mongodb.user_session — session CRUD for Slack project sessions."""

from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from crewai_productfeature_planner.mongodb.user_session import (
    USER_SESSION_COLLECTION,
    end_active_session,
    get_active_session,
    get_session,
    list_sessions,
    start_session,
    switch_session,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── helpers ──────────────────────────────────────────────────


def _mock_db(collection_mock: MagicMock | None = None) -> tuple[MagicMock, MagicMock]:
    """Return (mock_db, mock_collection) wired together."""
    col = collection_mock or MagicMock()
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=col)
    return db, col


# ── start_session ────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.user_session.get_db")
def test_start_session_returns_session_id(mock_get_db):
    """start_session should insert a doc and return a uuid hex."""
    col = MagicMock()
    col.insert_one.return_value = MagicMock(inserted_id="abc")
    col.update_one.return_value = MagicMock(modified_count=0)
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    sid = start_session(
        user_id="U123",
        channel="C456",
        project_id="proj-1",
        project_name="Test Project",
    )

    assert sid is not None
    assert len(sid) == 32  # uuid hex
    col.insert_one.assert_called_once()

    doc = col.insert_one.call_args[0][0]
    assert doc["user_id"] == "U123"
    assert doc["channel"] == "C456"
    assert doc["project_id"] == "proj-1"
    assert doc["project_name"] == "Test Project"
    assert doc["active"] is True
    assert doc["ended_at"] is None
    assert "started_at" in doc
    assert doc["session_id"] == sid


@patch("crewai_productfeature_planner.mongodb.user_session.get_db")
def test_start_session_ends_existing(mock_get_db):
    """start_session should end any existing active session first."""
    col = MagicMock()
    col.insert_one.return_value = MagicMock(inserted_id="abc")
    col.update_one.return_value = MagicMock(modified_count=1)
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    start_session(
        user_id="U123",
        channel="C456",
        project_id="proj-2",
        project_name="Project Two",
    )

    # update_one called for ending the previous session
    assert col.update_one.call_count == 1
    end_call = col.update_one.call_args
    assert end_call[0][0] == {"user_id": "U123", "active": True}
    assert end_call[0][1]["$set"]["active"] is False
    assert "ended_at" in end_call[0][1]["$set"]


@patch("crewai_productfeature_planner.mongodb.user_session.get_db")
def test_start_session_db_error(mock_get_db):
    """start_session should return None on insert failure."""
    col = MagicMock()
    col.update_one.return_value = MagicMock(modified_count=0)
    col.insert_one.side_effect = ServerSelectionTimeoutError("no server")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    sid = start_session(
        user_id="U123",
        channel="C456",
        project_id="proj-1",
        project_name="Test",
    )
    assert sid is None


# ── end_active_session ───────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.user_session.get_db")
def test_end_active_session_success(mock_get_db):
    """end_active_session should set active=False and return 1."""
    col = MagicMock()
    col.update_one.return_value = MagicMock(modified_count=1)
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    count = end_active_session(user_id="U123")

    assert count == 1
    call_args = col.update_one.call_args
    assert call_args[0][0] == {"user_id": "U123", "active": True}
    assert call_args[0][1]["$set"]["active"] is False
    assert "ended_at" in call_args[0][1]["$set"]


@patch("crewai_productfeature_planner.mongodb.user_session.get_db")
def test_end_active_session_none_active(mock_get_db):
    """end_active_session should return 0 when no active session exists."""
    col = MagicMock()
    col.update_one.return_value = MagicMock(modified_count=0)
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert end_active_session(user_id="U123") == 0


@patch("crewai_productfeature_planner.mongodb.user_session.get_db")
def test_end_active_session_db_error(mock_get_db):
    """end_active_session should return 0 on DB failure."""
    col = MagicMock()
    col.update_one.side_effect = ServerSelectionTimeoutError("down")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert end_active_session(user_id="U123") == 0


# ── switch_session ───────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.user_session.get_db")
def test_switch_session_delegates(mock_get_db):
    """switch_session should end + start, returning the new session_id."""
    col = MagicMock()
    col.update_one.return_value = MagicMock(modified_count=1)
    col.insert_one.return_value = MagicMock(inserted_id="new-id")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    sid = switch_session(
        user_id="U123",
        channel="C456",
        project_id="proj-new",
        project_name="New Project",
    )

    assert sid is not None
    assert len(sid) == 32
    # end_active_session + start_session both call update_one/insert_one
    assert col.update_one.call_count >= 1
    col.insert_one.assert_called_once()


# ── get_active_session ───────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.user_session.get_db")
def test_get_active_session_found(mock_get_db):
    """get_active_session should return the doc when active."""
    expected = {
        "session_id": "s1",
        "user_id": "U123",
        "project_id": "p1",
        "active": True,
    }
    col = MagicMock()
    col.find_one.return_value = expected
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    result = get_active_session("U123")

    assert result == expected
    col.find_one.assert_called_once_with(
        {"user_id": "U123", "active": True},
        {"_id": 0},
    )


@patch("crewai_productfeature_planner.mongodb.user_session.get_db")
def test_get_active_session_not_found(mock_get_db):
    """get_active_session should return None when no active session."""
    col = MagicMock()
    col.find_one.return_value = None
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert get_active_session("U123") is None


@patch("crewai_productfeature_planner.mongodb.user_session.get_db")
def test_get_active_session_db_error(mock_get_db):
    """get_active_session should return None on DB failure."""
    col = MagicMock()
    col.find_one.side_effect = ServerSelectionTimeoutError("down")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert get_active_session("U123") is None


# ── get_session ──────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.user_session.get_db")
def test_get_session_found(mock_get_db):
    """get_session should query by session_id."""
    expected = {"session_id": "s42", "project_id": "p1"}
    col = MagicMock()
    col.find_one.return_value = expected
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    result = get_session("s42")

    assert result == expected
    col.find_one.assert_called_once_with(
        {"session_id": "s42"},
        {"_id": 0},
    )


@patch("crewai_productfeature_planner.mongodb.user_session.get_db")
def test_get_session_db_error(mock_get_db):
    """get_session should return None on DB failure."""
    col = MagicMock()
    col.find_one.side_effect = ServerSelectionTimeoutError("down")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert get_session("s42") is None


# ── list_sessions ────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.user_session.get_db")
def test_list_sessions(mock_get_db):
    """list_sessions should return recent sessions sorted by started_at."""
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.__iter__ = MagicMock(return_value=iter([
        {"session_id": "s1", "user_id": "U123"},
        {"session_id": "s2", "user_id": "U123"},
    ]))

    col = MagicMock()
    col.find.return_value = mock_cursor
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    result = list_sessions("U123", limit=5)

    assert len(result) == 2
    col.find.assert_called_once_with({"user_id": "U123"}, {"_id": 0})
    mock_cursor.sort.assert_called_once_with("started_at", -1)
    mock_cursor.limit.assert_called_once_with(5)


@patch("crewai_productfeature_planner.mongodb.user_session.get_db")
def test_list_sessions_db_error(mock_get_db):
    """list_sessions should return [] on DB failure."""
    col = MagicMock()
    col.find.side_effect = ServerSelectionTimeoutError("down")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert list_sessions("U123") == []


# ── collection name ──────────────────────────────────────────


def test_collection_name():
    assert USER_SESSION_COLLECTION == "userSession"
