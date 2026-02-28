"""Tests for scripts.memory_loader — project memory loading and backstory enrichment."""

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.scripts.memory_loader import (
    _format_entries,
    enrich_backstory,
    enrich_backstory_for_run,
    load_project_memory_context,
    resolve_project_id,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── resolve_project_id ────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.client.get_db")
def test_resolve_project_id_found(mock_get_db):
    """resolve_project_id should return project_id from workingIdeas."""
    col = MagicMock()
    col.find_one.return_value = {"project_id": "proj-abc"}
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=col)
    mock_get_db.return_value = db

    result = resolve_project_id("run-123")

    assert result == "proj-abc"
    db.__getitem__.assert_called_with("workingIdeas")
    col.find_one.assert_called_once_with(
        {"run_id": "run-123"}, {"project_id": 1, "_id": 0},
    )


@patch("crewai_productfeature_planner.mongodb.client.get_db")
def test_resolve_project_id_not_linked(mock_get_db):
    """resolve_project_id should return None when no project_id."""
    col = MagicMock()
    col.find_one.return_value = {"run_id": "run-123"}  # no project_id
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=col)
    mock_get_db.return_value = db

    assert resolve_project_id("run-123") is None


@patch("crewai_productfeature_planner.mongodb.client.get_db")
def test_resolve_project_id_no_doc(mock_get_db):
    """resolve_project_id should return None when run not found."""
    col = MagicMock()
    col.find_one.return_value = None
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=col)
    mock_get_db.return_value = db

    assert resolve_project_id("nonexistent") is None


def test_resolve_project_id_empty_run_id():
    """resolve_project_id should return None for empty run_id."""
    assert resolve_project_id("") is None


@patch("crewai_productfeature_planner.mongodb.client.get_db")
def test_resolve_project_id_db_error(mock_get_db):
    """resolve_project_id should return None on DB error."""
    mock_get_db.side_effect = Exception("connection failed")

    assert resolve_project_id("run-123") is None


# ── _format_entries ───────────────────────────────────────────


def test_format_entries_empty():
    """Empty entries should return placeholder text."""
    assert _format_entries([]) == "(none configured)"


def test_format_entries_numbered():
    """Entries should be numbered by default."""
    entries = [
        {"content": "Alpha"},
        {"content": "Beta"},
    ]
    result = _format_entries(entries)
    assert result == "1. Alpha\n2. Beta"


def test_format_entries_unnumbered():
    """When numbered=False, entries use bullet points."""
    entries = [{"content": "One"}]
    result = _format_entries(entries, numbered=False)
    assert result == "• One"


def test_format_entries_with_kind():
    """Entries with 'kind' should show the kind label."""
    entries = [
        {"content": "https://docs.example.com", "kind": "link"},
    ]
    result = _format_entries(entries)
    assert result == "1. [link] https://docs.example.com"


def test_format_entries_skips_blank():
    """Entries with empty content should be skipped."""
    entries = [
        {"content": "Good"},
        {"content": ""},
        {"content": "   "},
        {"content": "Also good"},
    ]
    result = _format_entries(entries)
    assert "Good" in result
    assert "Also good" in result
    # Only 2 numbered entries
    assert result.startswith("1. Good")


# ── load_project_memory_context ───────────────────────────────


@patch(
    "crewai_productfeature_planner.mongodb.project_memory.get_project_memory",
)
def test_load_context_all_categories(mock_get_mem):
    """Context should include all three category sections."""
    mock_get_mem.return_value = {
        "project_id": "proj-1",
        "idea_iteration": [{"content": "Be concise"}],
        "knowledge": [{"content": "https://wiki.example.com", "kind": "link"}],
        "tools": [{"content": "PostgreSQL"}],
    }

    ctx = load_project_memory_context("proj-1")

    assert "PROJECT MEMORY" in ctx
    assert "Idea-Iteration Guardrails" in ctx
    assert "Be concise" in ctx
    assert "Knowledge References" in ctx
    assert "https://wiki.example.com" in ctx
    assert "Technology Stack" in ctx
    assert "PostgreSQL" in ctx


@patch(
    "crewai_productfeature_planner.mongodb.project_memory.get_project_memory",
)
def test_load_context_partial_categories(mock_get_mem):
    """Only populated categories should appear in context."""
    mock_get_mem.return_value = {
        "project_id": "proj-1",
        "idea_iteration": [],
        "knowledge": [],
        "tools": [{"content": "Redis"}, {"content": "FastAPI"}],
    }

    ctx = load_project_memory_context("proj-1")

    assert "Technology Stack" in ctx
    assert "Redis" in ctx
    assert "FastAPI" in ctx
    # Empty categories should NOT appear
    assert "Idea-Iteration Guardrails" not in ctx
    assert "Knowledge References" not in ctx


@patch(
    "crewai_productfeature_planner.mongodb.project_memory.get_project_memory",
)
def test_load_context_all_empty(mock_get_mem):
    """All-empty categories should return empty string."""
    mock_get_mem.return_value = {
        "project_id": "proj-1",
        "idea_iteration": [],
        "knowledge": [],
        "tools": [],
    }

    assert load_project_memory_context("proj-1") == ""


@patch(
    "crewai_productfeature_planner.mongodb.project_memory.get_project_memory",
)
def test_load_context_no_doc(mock_get_mem):
    """Missing doc should return empty string."""
    mock_get_mem.return_value = None

    assert load_project_memory_context("proj-1") == ""


def test_load_context_empty_project_id():
    """Empty project_id should return empty string without DB call."""
    assert load_project_memory_context("") == ""


def test_load_context_none_project_id():
    """None project_id should return empty string."""
    assert load_project_memory_context(None) == ""


@patch(
    "crewai_productfeature_planner.mongodb.project_memory.get_project_memory",
)
def test_load_context_db_error(mock_get_mem):
    """DB error should return empty string."""
    mock_get_mem.side_effect = Exception("connection lost")

    assert load_project_memory_context("proj-1") == ""


# ── enrich_backstory ──────────────────────────────────────────


@patch(
    "crewai_productfeature_planner.scripts.memory_loader.load_project_memory_context",
)
def test_enrich_backstory_appends(mock_load):
    """enrich_backstory should append context to backstory."""
    mock_load.return_value = "\n=== PROJECT MEMORY ===\nBe concise"

    result = enrich_backstory("I am a PM.", "proj-1")

    assert result.startswith("I am a PM.")
    assert "PROJECT MEMORY" in result
    assert "Be concise" in result
    mock_load.assert_called_once_with("proj-1")


@patch(
    "crewai_productfeature_planner.scripts.memory_loader.load_project_memory_context",
)
def test_enrich_backstory_empty_context(mock_load):
    """enrich_backstory should return original when context is empty."""
    mock_load.return_value = ""

    result = enrich_backstory("I am a PM.", "proj-1")

    assert result == "I am a PM."


def test_enrich_backstory_none_project_id():
    """enrich_backstory should return original when project_id is None."""
    result = enrich_backstory("I am a PM.", None)
    assert result == "I am a PM."


def test_enrich_backstory_empty_project_id():
    """enrich_backstory should return original when project_id is empty."""
    result = enrich_backstory("I am a PM.", "")
    assert result == "I am a PM."


# ── enrich_backstory_for_run ──────────────────────────────────


@patch(
    "crewai_productfeature_planner.scripts.memory_loader.resolve_project_id",
)
@patch(
    "crewai_productfeature_planner.scripts.memory_loader.enrich_backstory",
)
def test_enrich_backstory_for_run_delegates(mock_enrich, mock_resolve):
    """enrich_backstory_for_run should resolve project_id then enrich."""
    mock_resolve.return_value = "proj-X"
    mock_enrich.return_value = "enriched backstory"

    result = enrich_backstory_for_run("Original BS", "run-42")

    assert result == "enriched backstory"
    mock_resolve.assert_called_once_with("run-42")
    mock_enrich.assert_called_once_with("Original BS", "proj-X")


@patch(
    "crewai_productfeature_planner.scripts.memory_loader.resolve_project_id",
)
@patch(
    "crewai_productfeature_planner.scripts.memory_loader.enrich_backstory",
)
def test_enrich_backstory_for_run_no_project(mock_enrich, mock_resolve):
    """enrich_backstory_for_run should pass None when project not linked."""
    mock_resolve.return_value = None
    mock_enrich.return_value = "Original BS"

    result = enrich_backstory_for_run("Original BS", "run-42")

    assert result == "Original BS"
    mock_enrich.assert_called_once_with("Original BS", None)
