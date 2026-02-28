"""Tests for apis.slack.session_manager — in-memory session state cache."""

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.apis.slack.session_manager import (
    _active_sessions,
    _lock,
    _pending_memory_entries,
    _pending_project_creates,
    activate_project,
    deactivate_session,
    ensure_session_loaded,
    get_cached_session,
    get_project_id_for_user,
    mark_pending_create,
    mark_pending_memory,
    pop_pending_create,
    pop_pending_memory,
)


@pytest.fixture(autouse=True)
def _clean_state():
    """Clear module-level dicts before each test."""
    _active_sessions.clear()
    _pending_project_creates.clear()
    _pending_memory_entries.clear()
    yield
    _active_sessions.clear()
    _pending_project_creates.clear()
    _pending_memory_entries.clear()


# ── get_cached_session ───────────────────────────────────────


def test_get_cached_session_empty():
    assert get_cached_session("U123") is None


def test_get_cached_session_found():
    _active_sessions["U123"] = {"project_id": "p1"}
    assert get_cached_session("U123") == {"project_id": "p1"}


# ── activate_project ────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.user_session.start_session")
def test_activate_project_success(mock_start):
    mock_start.return_value = "sid-123"

    result = activate_project(
        user_id="U1",
        channel="C1",
        project_id="p1",
        project_name="My Project",
    )

    assert result == "sid-123"
    assert "U1" in _active_sessions
    session = _active_sessions["U1"]
    assert session["project_id"] == "p1"
    assert session["project_name"] == "My Project"
    assert session["active"] is True


@patch("crewai_productfeature_planner.mongodb.user_session.start_session")
def test_activate_project_failure(mock_start):
    mock_start.return_value = None

    result = activate_project(
        user_id="U1",
        channel="C1",
        project_id="p1",
        project_name="My Project",
    )

    assert result is None
    assert "U1" not in _active_sessions


# ── deactivate_session ───────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.user_session.end_active_session")
def test_deactivate_session_success(mock_end):
    mock_end.return_value = 1
    _active_sessions["U1"] = {"project_id": "p1"}

    count = deactivate_session("U1")

    assert count == 1
    assert "U1" not in _active_sessions
    mock_end.assert_called_once_with(user_id="U1")


@patch("crewai_productfeature_planner.mongodb.user_session.end_active_session")
def test_deactivate_session_no_active(mock_end):
    mock_end.return_value = 0
    count = deactivate_session("U1")
    assert count == 0


# ── ensure_session_loaded ────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.user_session.get_active_session")
def test_ensure_loaded_from_cache(mock_get):
    """Should return cached session without calling MongoDB."""
    _active_sessions["U1"] = {"project_id": "p1"}

    result = ensure_session_loaded("U1")

    assert result == {"project_id": "p1"}
    mock_get.assert_not_called()


@patch("crewai_productfeature_planner.mongodb.user_session.get_active_session")
def test_ensure_loaded_from_db(mock_get):
    """Should load from MongoDB when cache is empty."""
    mock_get.return_value = {"project_id": "p2", "active": True}

    result = ensure_session_loaded("U1")

    assert result == {"project_id": "p2", "active": True}
    assert _active_sessions["U1"]["project_id"] == "p2"
    mock_get.assert_called_once_with("U1")


@patch("crewai_productfeature_planner.mongodb.user_session.get_active_session")
def test_ensure_loaded_no_session(mock_get):
    """Should return None when no session in cache or DB."""
    mock_get.return_value = None
    assert ensure_session_loaded("U1") is None
    assert "U1" not in _active_sessions


# ── get_project_id_for_user ──────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.user_session.get_active_session")
def test_get_project_id_cached(mock_get):
    _active_sessions["U1"] = {"project_id": "p1", "active": True}
    assert get_project_id_for_user("U1") == "p1"
    mock_get.assert_not_called()


@patch("crewai_productfeature_planner.mongodb.user_session.get_active_session")
def test_get_project_id_none(mock_get):
    mock_get.return_value = None
    assert get_project_id_for_user("U1") is None


# ── pending project creates ─────────────────────────────────


def test_mark_pending_create():
    mark_pending_create("U1", "C1", "ts1")
    assert _pending_project_creates["U1"] == {"channel": "C1", "thread_ts": "ts1"}


def test_pop_pending_create_found():
    _pending_project_creates["U1"] = {"channel": "C1", "thread_ts": "ts1"}

    result = pop_pending_create("U1")

    assert result == {"channel": "C1", "thread_ts": "ts1"}
    assert "U1" not in _pending_project_creates


def test_pop_pending_create_not_found():
    assert pop_pending_create("U1") is None


def test_mark_then_pop_cycle():
    """Full cycle: mark, pop returns data, second pop returns None."""
    mark_pending_create("U1", "C1", "ts1")
    result = pop_pending_create("U1")
    assert result is not None
    assert pop_pending_create("U1") is None


# ── pending memory entries ────────────────────────────────────


def test_mark_pending_memory():
    mark_pending_memory("U1", "C1", "ts1", "idea_iteration", "proj-1")
    assert _pending_memory_entries["U1"] == {
        "channel": "C1",
        "thread_ts": "ts1",
        "category": "idea_iteration",
        "project_id": "proj-1",
    }


def test_pop_pending_memory_found():
    _pending_memory_entries["U1"] = {
        "channel": "C1",
        "thread_ts": "ts1",
        "category": "tools",
        "project_id": "proj-2",
    }

    result = pop_pending_memory("U1")

    assert result == {
        "channel": "C1",
        "thread_ts": "ts1",
        "category": "tools",
        "project_id": "proj-2",
    }
    assert "U1" not in _pending_memory_entries


def test_pop_pending_memory_not_found():
    assert pop_pending_memory("U1") is None


def test_mark_then_pop_memory_cycle():
    """Full memory cycle: mark, pop returns data, second pop returns None."""
    mark_pending_memory("U1", "C1", "ts1", "knowledge", "proj-3")
    result = pop_pending_memory("U1")
    assert result is not None
    assert result["category"] == "knowledge"
    assert result["project_id"] == "proj-3"
    assert pop_pending_memory("U1") is None


def test_pending_memory_independent_of_pending_create():
    """Memory and create pending entries should be independent."""
    mark_pending_create("U1", "C1", "ts1")
    mark_pending_memory("U1", "C1", "ts2", "tools", "proj-1")

    # Pop one should not affect the other
    create_data = pop_pending_create("U1")
    assert create_data is not None

    memory_data = pop_pending_memory("U1")
    assert memory_data is not None
    assert memory_data["category"] == "tools"
