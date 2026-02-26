"""Tests for mongodb.agent_interactions.repository — interaction tracking."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from crewai_productfeature_planner.mongodb.agent_interactions.repository import (
    AGENT_INTERACTIONS_COLLECTION,
    find_interactions,
    find_interactions_by_intent,
    find_interactions_by_source,
    get_interaction,
    list_interactions,
    log_interaction,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── collection name ───────────────────────────────────────────


def test_collection_name():
    assert AGENT_INTERACTIONS_COLLECTION == "agentInteraction"


# ── log_interaction ───────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.agent_interactions.repository.get_db")
def test_log_interaction_success(mock_get_db):
    """log_interaction should insert a document and return the interaction_id."""
    mock_collection = MagicMock()
    mock_result = MagicMock()
    mock_result.inserted_id = "abc123"
    mock_collection.insert_one.return_value = mock_result
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = log_interaction(
        source="slack",
        user_message="create a prd for a fitness app",
        intent="create_prd",
        agent_response="Got it! Starting a PRD flow...",
        idea="fitness app",
        channel="C123",
        thread_ts="1234.5678",
        user_id="U999",
    )

    assert result is not None
    assert isinstance(result, str)
    assert len(result) == 32  # uuid hex

    mock_collection.insert_one.assert_called_once()
    doc = mock_collection.insert_one.call_args[0][0]
    assert doc["source"] == "slack"
    assert doc["user_message"] == "create a prd for a fitness app"
    assert doc["intent"] == "create_prd"
    assert doc["agent_response"] == "Got it! Starting a PRD flow..."
    assert doc["idea"] == "fitness app"
    assert doc["channel"] == "C123"
    assert doc["thread_ts"] == "1234.5678"
    assert doc["user_id"] == "U999"
    assert isinstance(doc["created_at"], datetime)
    assert doc["created_at"].tzinfo == timezone.utc


@patch("crewai_productfeature_planner.mongodb.agent_interactions.repository.get_db")
def test_log_interaction_minimal(mock_get_db):
    """log_interaction should work with only required fields."""
    mock_collection = MagicMock()
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = log_interaction(
        source="cli",
        user_message="my idea",
        intent="create_prd",
        agent_response="Idea captured",
    )

    assert result is not None
    doc = mock_collection.insert_one.call_args[0][0]
    assert doc["source"] == "cli"
    assert doc["channel"] is None
    assert doc["thread_ts"] is None
    assert doc["run_id"] is None
    assert doc["conversation_history"] is None
    assert doc["metadata"] is None


@patch("crewai_productfeature_planner.mongodb.agent_interactions.repository.get_db")
def test_log_interaction_with_metadata(mock_get_db):
    """log_interaction should store metadata and conversation_history."""
    mock_collection = MagicMock()
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    meta = {"interactive": True}

    result = log_interaction(
        source="slack",
        user_message="create a prd interactively",
        intent="create_prd",
        agent_response="Starting interactive flow",
        conversation_history=history,
        metadata=meta,
    )

    assert result is not None
    doc = mock_collection.insert_one.call_args[0][0]
    assert doc["conversation_history"] == history
    assert doc["metadata"] == meta


@patch("crewai_productfeature_planner.mongodb.agent_interactions.repository.get_db")
def test_log_interaction_db_error(mock_get_db):
    """log_interaction should return None on database errors."""
    mock_collection = MagicMock()
    mock_collection.insert_one.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = log_interaction(
        source="slack",
        user_message="test",
        intent="help",
        agent_response="help text",
    )

    assert result is None


# ── get_interaction ───────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.agent_interactions.repository.get_db")
def test_get_interaction_found(mock_get_db):
    """get_interaction should return the document when found."""
    doc = {"interaction_id": "abc123", "source": "slack", "intent": "help"}
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = doc
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = get_interaction("abc123")
    assert result == doc
    mock_collection.find_one.assert_called_once_with({"interaction_id": "abc123"})


@patch("crewai_productfeature_planner.mongodb.agent_interactions.repository.get_db")
def test_get_interaction_not_found(mock_get_db):
    """get_interaction should return None when not found."""
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = None
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    assert get_interaction("nonexistent") is None


@patch("crewai_productfeature_planner.mongodb.agent_interactions.repository.get_db")
def test_get_interaction_db_error(mock_get_db):
    """get_interaction should return None on database errors."""
    mock_collection = MagicMock()
    mock_collection.find_one.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    assert get_interaction("abc123") is None


# ── find_interactions_by_source ───────────────────────────────


@patch("crewai_productfeature_planner.mongodb.agent_interactions.repository.get_db")
def test_find_by_source(mock_get_db):
    """find_interactions_by_source should filter by source."""
    docs = [{"source": "slack", "intent": "help"}]
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = docs
    mock_collection = MagicMock()
    mock_collection.find.return_value = mock_cursor
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = find_interactions_by_source("slack", limit=50)
    assert result == docs
    mock_collection.find.assert_called_once_with({"source": "slack"})
    mock_cursor.sort.assert_called_once_with("created_at", -1)
    mock_cursor.limit.assert_called_once_with(50)


@patch("crewai_productfeature_planner.mongodb.agent_interactions.repository.get_db")
def test_find_by_source_db_error(mock_get_db):
    """find_interactions_by_source should return [] on error."""
    mock_collection = MagicMock()
    mock_collection.find.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    assert find_interactions_by_source("slack") == []


# ── find_interactions_by_intent ───────────────────────────────


@patch("crewai_productfeature_planner.mongodb.agent_interactions.repository.get_db")
def test_find_by_intent(mock_get_db):
    """find_interactions_by_intent should filter by intent."""
    docs = [{"intent": "create_prd"}]
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = docs
    mock_collection = MagicMock()
    mock_collection.find.return_value = mock_cursor
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = find_interactions_by_intent("create_prd")
    assert result == docs
    mock_collection.find.assert_called_once_with({"intent": "create_prd"})


@patch("crewai_productfeature_planner.mongodb.agent_interactions.repository.get_db")
def test_find_by_intent_db_error(mock_get_db):
    """find_interactions_by_intent should return [] on error."""
    mock_collection = MagicMock()
    mock_collection.find.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    assert find_interactions_by_intent("help") == []


# ── find_interactions (flexible query) ────────────────────────


@patch("crewai_productfeature_planner.mongodb.agent_interactions.repository.get_db")
def test_find_interactions_no_filters(mock_get_db):
    """find_interactions with no filters should pass empty query."""
    docs = [{"intent": "help"}]
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = docs
    mock_collection = MagicMock()
    mock_collection.find.return_value = mock_cursor
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = find_interactions()
    assert result == docs
    mock_collection.find.assert_called_once_with({})


@patch("crewai_productfeature_planner.mongodb.agent_interactions.repository.get_db")
def test_find_interactions_all_filters(mock_get_db):
    """find_interactions should combine all provided filters."""
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    docs = []
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = docs
    mock_collection = MagicMock()
    mock_collection.find.return_value = mock_cursor
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = find_interactions(
        source="cli",
        intent="create_prd",
        user_id="cli_user",
        run_id="run123",
        since=since,
        limit=10,
    )

    assert result == docs
    expected_query = {
        "source": "cli",
        "intent": "create_prd",
        "user_id": "cli_user",
        "run_id": "run123",
        "created_at": {"$gte": since},
    }
    mock_collection.find.assert_called_once_with(expected_query)
    mock_cursor.limit.assert_called_once_with(10)


@patch("crewai_productfeature_planner.mongodb.agent_interactions.repository.get_db")
def test_find_interactions_db_error(mock_get_db):
    """find_interactions should return [] on error."""
    mock_collection = MagicMock()
    mock_collection.find.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    assert find_interactions(source="slack") == []


# ── list_interactions ─────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.agent_interactions.repository.get_db")
def test_list_interactions(mock_get_db):
    """list_interactions should return all interactions with default limit."""
    docs = [{"intent": "help"}, {"intent": "create_prd"}]
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = docs
    mock_collection = MagicMock()
    mock_collection.find.return_value = mock_cursor
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = list_interactions()
    assert result == docs
    mock_collection.find.assert_called_once_with()
    mock_cursor.sort.assert_called_once_with("created_at", -1)
    mock_cursor.limit.assert_called_once_with(100)


@patch("crewai_productfeature_planner.mongodb.agent_interactions.repository.get_db")
def test_list_interactions_custom_limit(mock_get_db):
    """list_interactions should respect custom limit."""
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = []
    mock_collection = MagicMock()
    mock_collection.find.return_value = mock_cursor
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    list_interactions(limit=5)
    mock_cursor.limit.assert_called_once_with(5)


@patch("crewai_productfeature_planner.mongodb.agent_interactions.repository.get_db")
def test_list_interactions_db_error(mock_get_db):
    """list_interactions should return [] on error."""
    mock_collection = MagicMock()
    mock_collection.find.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    assert list_interactions() == []
