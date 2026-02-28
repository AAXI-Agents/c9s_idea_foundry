"""Tests for mongodb.project_memory.repository — CRUD for projectMemory collection."""

from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from crewai_productfeature_planner.mongodb.project_memory.repository import (
    PROJECT_MEMORY_COLLECTION,
    MemoryCategory,
    add_memory_entry,
    clear_category,
    delete_memory_entry,
    get_memories_for_agent,
    get_project_memory,
    list_memory_entries,
    replace_category_entries,
    upsert_project_memory,
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


# ── MemoryCategory ───────────────────────────────────────────


def test_memory_category_values():
    """MemoryCategory should have three values matching collection keys."""
    assert MemoryCategory.IDEA_ITERATION.value == "idea_iteration"
    assert MemoryCategory.KNOWLEDGE.value == "knowledge"
    assert MemoryCategory.TOOLS.value == "tools"


def test_memory_category_is_str():
    """MemoryCategory members should be usable as strings."""
    assert isinstance(MemoryCategory.IDEA_ITERATION, str)
    assert MemoryCategory.KNOWLEDGE == "knowledge"


# ── upsert_project_memory ────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_upsert_creates_scaffold(mock_get_db):
    """upsert_project_memory should create an empty scaffold on first call."""
    col = MagicMock()
    col.update_one.return_value = MagicMock(upserted_id="new_id")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    result = upsert_project_memory("proj-1")

    assert result is True
    col.update_one.assert_called_once()
    args, kwargs = col.update_one.call_args
    assert args[0] == {"project_id": "proj-1"}
    # $setOnInsert should contain the scaffold
    set_on_insert = args[1]["$setOnInsert"]
    assert set_on_insert["project_id"] == "proj-1"
    assert set_on_insert["idea_iteration"] == []
    assert set_on_insert["knowledge"] == []
    assert set_on_insert["tools"] == []
    assert kwargs.get("upsert") is True


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_upsert_idempotent(mock_get_db):
    """upsert_project_memory should return True even if doc already exists."""
    col = MagicMock()
    col.update_one.return_value = MagicMock(upserted_id=None)
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    result = upsert_project_memory("proj-1")

    assert result is True


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_upsert_db_error_returns_false(mock_get_db):
    """upsert_project_memory should return False on DB error."""
    col = MagicMock()
    col.update_one.side_effect = ServerSelectionTimeoutError("timeout")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    result = upsert_project_memory("proj-1")

    assert result is False


# ── get_project_memory ────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_get_project_memory_returns_doc(mock_get_db):
    """get_project_memory should return the document without _id."""
    expected = {
        "project_id": "proj-1",
        "idea_iteration": [{"content": "Be concise"}],
        "knowledge": [],
        "tools": [],
    }
    col = MagicMock()
    col.find_one.return_value = expected
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    doc = get_project_memory("proj-1")

    assert doc == expected
    col.find_one.assert_called_once_with(
        {"project_id": "proj-1"}, {"_id": 0},
    )


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_get_project_memory_not_found(mock_get_db):
    """get_project_memory should return None when doc doesn't exist."""
    col = MagicMock()
    col.find_one.return_value = None
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert get_project_memory("nonexistent") is None


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_get_project_memory_db_error(mock_get_db):
    """get_project_memory should return None on DB error."""
    col = MagicMock()
    col.find_one.side_effect = ServerSelectionTimeoutError("timeout")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert get_project_memory("proj-1") is None


# ── list_memory_entries ───────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_list_memory_entries_returns_category(mock_get_db):
    """list_memory_entries should return the correct category array."""
    doc = {
        "project_id": "proj-1",
        "idea_iteration": [{"content": "Focus on MVP"}],
        "knowledge": [{"content": "https://example.com", "kind": "link"}],
        "tools": [],
    }
    col = MagicMock()
    col.find_one.return_value = doc
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    entries = list_memory_entries("proj-1", MemoryCategory.IDEA_ITERATION)
    assert len(entries) == 1
    assert entries[0]["content"] == "Focus on MVP"


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_list_memory_entries_empty_on_missing(mock_get_db):
    """list_memory_entries should return [] when no document found."""
    col = MagicMock()
    col.find_one.return_value = None
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert list_memory_entries("proj-1", MemoryCategory.TOOLS) == []


# ── get_memories_for_agent ────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_get_memories_for_agent_all_categories(mock_get_db):
    """get_memories_for_agent should return all three categories."""
    doc = {
        "project_id": "proj-1",
        "idea_iteration": [{"content": "a"}],
        "knowledge": [{"content": "b", "kind": "note"}],
        "tools": [{"content": "c"}],
    }
    col = MagicMock()
    col.find_one.return_value = doc
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    result = get_memories_for_agent("proj-1", "Product Manager")

    assert result["idea_iteration"] == [{"content": "a"}]
    assert result["knowledge"] == [{"content": "b", "kind": "note"}]
    assert result["tools"] == [{"content": "c"}]


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_get_memories_for_agent_missing_doc(mock_get_db):
    """get_memories_for_agent should return empty lists for all categories."""
    col = MagicMock()
    col.find_one.return_value = None
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    result = get_memories_for_agent("proj-1", "Idea Refiner")

    assert result == {
        "idea_iteration": [],
        "knowledge": [],
        "tools": [],
    }


# ── add_memory_entry ──────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_add_memory_entry_appends(mock_get_db):
    """add_memory_entry should $push to the correct category."""
    col = MagicMock()
    col.update_one.return_value = MagicMock(
        modified_count=1, upserted_id=None, matched_count=1,
    )
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    result = add_memory_entry(
        "proj-1", MemoryCategory.IDEA_ITERATION,
        "Be concise", added_by="U123",
    )

    assert result is True
    # Should have been called twice: upsert scaffold + push
    assert col.update_one.call_count == 2
    push_call = col.update_one.call_args_list[1]
    push_op = push_call[0][1]
    assert "idea_iteration" in push_op["$push"]
    entry = push_op["$push"]["idea_iteration"]
    assert entry["content"] == "Be concise"
    assert entry["added_by"] == "U123"


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_add_memory_entry_knowledge_with_kind(mock_get_db):
    """add_memory_entry should include 'kind' for knowledge entries."""
    col = MagicMock()
    col.update_one.return_value = MagicMock(
        modified_count=1, upserted_id=None, matched_count=1,
    )
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    add_memory_entry(
        "proj-1", MemoryCategory.KNOWLEDGE,
        "https://docs.example.com", kind="link",
    )

    push_call = col.update_one.call_args_list[1]
    entry = push_call[0][1]["$push"]["knowledge"]
    assert entry["kind"] == "link"
    assert entry["content"] == "https://docs.example.com"


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_add_memory_entry_tools_no_kind(mock_get_db):
    """add_memory_entry should not include 'kind' for non-knowledge entries."""
    col = MagicMock()
    col.update_one.return_value = MagicMock(
        modified_count=1, upserted_id=None, matched_count=1,
    )
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    add_memory_entry("proj-1", MemoryCategory.TOOLS, "PostgreSQL")

    push_call = col.update_one.call_args_list[1]
    entry = push_call[0][1]["$push"]["tools"]
    assert "kind" not in entry


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_add_memory_entry_db_error(mock_get_db):
    """add_memory_entry should return False on DB error."""
    col = MagicMock()
    # First call (upsert) succeeds, second ($push) fails
    col.update_one.side_effect = [
        MagicMock(upserted_id=None),
        ServerSelectionTimeoutError("timeout"),
    ]
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    result = add_memory_entry("proj-1", MemoryCategory.TOOLS, "Redis")

    assert result is False


# ── replace_category_entries ──────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_replace_category_entries(mock_get_db):
    """replace_category_entries should $set the category array."""
    col = MagicMock()
    col.update_one.return_value = MagicMock(
        modified_count=1, upserted_id=None, matched_count=1,
    )
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    new_entries = [
        {"content": "Entry A", "added_by": "system"},
        {"content": "Entry B", "added_by": "U456"},
    ]
    result = replace_category_entries(
        "proj-1", MemoryCategory.TOOLS, new_entries,
    )

    assert result is True
    # 2 calls: upsert scaffold + $set
    set_call = col.update_one.call_args_list[1]
    set_op = set_call[0][1]["$set"]
    assert set_op["tools"] == new_entries


# ── clear_category ────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_clear_category(mock_get_db):
    """clear_category should set the category to empty list."""
    col = MagicMock()
    col.update_one.return_value = MagicMock(
        modified_count=1, upserted_id=None, matched_count=1,
    )
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    result = clear_category("proj-1", MemoryCategory.IDEA_ITERATION)

    assert result is True
    set_call = col.update_one.call_args_list[1]
    set_op = set_call[0][1]["$set"]
    assert set_op["idea_iteration"] == []


# ── delete_memory_entry ───────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_delete_memory_entry_removes(mock_get_db):
    """delete_memory_entry should $pull the matching entry."""
    col = MagicMock()
    col.update_one.return_value = MagicMock(modified_count=1)
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    result = delete_memory_entry(
        "proj-1", MemoryCategory.KNOWLEDGE, "https://old.link",
    )

    assert result is True
    args = col.update_one.call_args[0]
    assert args[0] == {"project_id": "proj-1"}
    assert args[1]["$pull"]["knowledge"] == {"content": "https://old.link"}


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_delete_memory_entry_not_found(mock_get_db):
    """delete_memory_entry should return False when nothing removed."""
    col = MagicMock()
    col.update_one.return_value = MagicMock(modified_count=0)
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    result = delete_memory_entry(
        "proj-1", MemoryCategory.TOOLS, "nonexistent",
    )

    assert result is False


@patch("crewai_productfeature_planner.mongodb.project_memory.repository.get_db")
def test_delete_memory_entry_db_error(mock_get_db):
    """delete_memory_entry should return False on DB error."""
    col = MagicMock()
    col.update_one.side_effect = ServerSelectionTimeoutError("down")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    result = delete_memory_entry(
        "proj-1", MemoryCategory.IDEA_ITERATION, "something",
    )

    assert result is False


# ── collection name ───────────────────────────────────────────


def test_collection_name():
    """PROJECT_MEMORY_COLLECTION should be the expected string."""
    assert PROJECT_MEMORY_COLLECTION == "projectMemory"
