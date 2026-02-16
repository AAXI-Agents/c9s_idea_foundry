"""Tests for mongodb.working_ideas.repository — save_iteration, save_failed, find_unfinalized, get_run_documents, mark_completed."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from crewai_productfeature_planner.mongodb.working_ideas.repository import (
    WORKING_COLLECTION,
    find_unfinalized,
    get_run_documents,
    mark_completed,
    save_failed,
    save_iteration,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── save_iteration ────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_iteration_inserts_doc(mock_get_db):
    """save_iteration should insert into workingIdeas."""
    mock_collection = MagicMock()
    mock_collection.insert_one.return_value = MagicMock(inserted_id="abc123")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = save_iteration(
        run_id="run-1", idea="Dark mode", iteration=2, draft={"executive_summary": "# Draft v2"}
    )

    mock_db.__getitem__.assert_called_with(WORKING_COLLECTION)
    mock_collection.insert_one.assert_called_once()
    doc = mock_collection.insert_one.call_args[0][0]
    assert doc["run_id"] == "run-1"
    assert doc["idea"] == "Dark mode"
    assert doc["iteration"] == 2
    assert doc["draft"] == {"executive_summary": "# Draft v2"}
    assert result == "abc123"


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_iteration_includes_critique(mock_get_db):
    """Critique field should be saved when provided."""
    mock_collection = MagicMock()
    mock_collection.insert_one.return_value = MagicMock(inserted_id="x")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    save_iteration(
        run_id="r1", idea="X", iteration=1, draft={"exec": "D"}, critique="Needs work"
    )

    doc = mock_collection.insert_one.call_args[0][0]
    assert doc["critique"] == "Needs work"


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_iteration_includes_step(mock_get_db):
    """save_iteration should persist the step label."""
    mock_collection = MagicMock()
    mock_collection.insert_one.return_value = MagicMock(inserted_id="s1")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    save_iteration(
        run_id="r1", idea="X", iteration=1, draft={"exec": "D"}, step="critique"
    )

    doc = mock_collection.insert_one.call_args[0][0]
    assert doc["step"] == "critique"


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_iteration_returns_none_on_db_error(mock_get_db):
    """save_iteration should catch PyMongo errors and return None."""
    mock_collection = MagicMock()
    mock_collection.insert_one.side_effect = ServerSelectionTimeoutError(
        "connection refused"
    )
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = save_iteration(
        run_id="r1", idea="X", iteration=1, draft={"exec": "D"}
    )
    assert result is None


# ── save_failed ─────────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_failed_inserts_doc(mock_get_db):
    """save_failed should insert a failure record into workingIdeas."""
    mock_collection = MagicMock()
    mock_collection.insert_one.return_value = MagicMock(inserted_id="fail123")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = save_failed(
        run_id="run-x",
        idea="Widget",
        iteration=2,
        error="LLM timeout",
        draft={"executive_summary": "# Partial"},
        step="critique",
    )

    mock_db.__getitem__.assert_called_with(WORKING_COLLECTION)
    mock_collection.insert_one.assert_called_once()
    doc = mock_collection.insert_one.call_args[0][0]
    assert doc["run_id"] == "run-x"
    assert doc["status"] == "failed"
    assert doc["error"] == "LLM timeout"
    assert doc["draft"] == {"executive_summary": "# Partial"}
    assert doc["step"] == "critique"
    assert doc["iteration"] == 2
    assert result == "fail123"


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_failed_returns_none_on_db_error(mock_get_db):
    """save_failed should catch PyMongo errors and return None."""
    mock_collection = MagicMock()
    mock_collection.insert_one.side_effect = ServerSelectionTimeoutError(
        "connection refused"
    )
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = save_failed(
        run_id="r1", idea="X", iteration=1, error="boom"
    )
    assert result is None


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_failed_minimal_fields(mock_get_db):
    """save_failed with only required fields should use empty defaults."""
    mock_collection = MagicMock()
    mock_collection.insert_one.return_value = MagicMock(inserted_id="f1")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    save_failed(run_id="r1", idea="X", iteration=1, error="err")

    doc = mock_collection.insert_one.call_args[0][0]
    assert doc["draft"] == {}
    assert doc["step"] == ""


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_failed_with_extra_kwargs(mock_get_db):
    """save_failed should forward extra kwargs (e.g. section_key) into the document."""
    mock_collection = MagicMock()
    mock_collection.insert_one.return_value = MagicMock(inserted_id="f2")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    save_failed(
        run_id="r2", idea="Y", iteration=3, error="quota",
        step="draft_competitive_landscape",
        section_key="competitive_landscape",
        section_title="Competitive Landscape",
    )

    doc = mock_collection.insert_one.call_args[0][0]
    assert doc["section_key"] == "competitive_landscape"
    assert doc["section_title"] == "Competitive Landscape"
    assert doc["step"] == "draft_competitive_landscape"


# ── find_unfinalized ────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_find_unfinalized_returns_runs(mock_get_db):
    """find_unfinalized should return run summaries not in finalizeIdeas."""
    ts = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
    agg_results = [
        {
            "_id": "run-abc",
            "idea": "Dark mode",
            "iteration": 3,
            "created_at": ts,
            "sections": ["executive_summary", "problem_statement"],
        }
    ]

    mock_finalized_col = MagicMock()
    mock_finalized_col.distinct.return_value = ["run-xyz"]

    mock_working_col = MagicMock()
    mock_working_col.aggregate.return_value = agg_results
    mock_working_col.distinct.return_value = []  # no completed run_ids

    def getitem(name):
        if name == "finalizeIdeas":
            return mock_finalized_col
        return mock_working_col

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=getitem)
    mock_get_db.return_value = mock_db

    runs = find_unfinalized()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run-abc"
    assert runs[0]["idea"] == "Dark mode"
    assert runs[0]["iteration"] == 3
    assert "executive_summary" in runs[0]["sections"]


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_find_unfinalized_empty_when_all_finalized(mock_get_db):
    """find_unfinalized should return empty if every run is finalized."""
    mock_finalized_col = MagicMock()
    mock_finalized_col.distinct.return_value = ["run-1"]

    mock_working_col = MagicMock()
    mock_working_col.aggregate.return_value = []
    mock_working_col.distinct.return_value = []  # no completed run_ids

    def getitem(name):
        if name == "finalizeIdeas":
            return mock_finalized_col
        return mock_working_col

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=getitem)
    mock_get_db.return_value = mock_db

    runs = find_unfinalized()
    assert runs == []


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_find_unfinalized_returns_empty_on_error(mock_get_db):
    """find_unfinalized should return [] on database errors."""
    mock_get_db.side_effect = ServerSelectionTimeoutError("timeout")
    assert find_unfinalized() == []


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_find_unfinalized_filters_none_sections(mock_get_db):
    """find_unfinalized should strip None/empty section keys."""
    agg_results = [
        {
            "_id": "run-1",
            "idea": "Test",
            "iteration": 1,
            "created_at": None,
            "sections": ["executive_summary", None, ""],
        }
    ]

    mock_finalized_col = MagicMock()
    mock_finalized_col.distinct.return_value = []
    mock_working_col = MagicMock()
    mock_working_col.aggregate.return_value = agg_results
    mock_working_col.distinct.return_value = []  # no completed run_ids

    def getitem(name):
        if name == "finalizeIdeas":
            return mock_finalized_col
        return mock_working_col

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=getitem)
    mock_get_db.return_value = mock_db

    runs = find_unfinalized()
    assert runs[0]["sections"] == ["executive_summary"]


# ── get_run_documents ───────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_get_run_documents_returns_sorted_docs(mock_get_db):
    """get_run_documents should return all docs for a run sorted ascending."""
    docs = [
        {"run_id": "run-1", "iteration": 1, "section_key": "executive_summary"},
        {"run_id": "run-1", "iteration": 2, "section_key": "problem_statement"},
    ]
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = docs

    mock_collection = MagicMock()
    mock_collection.find.return_value = mock_cursor

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = get_run_documents("run-1")
    assert result == docs
    mock_collection.find.assert_called_once_with(
        {"run_id": "run-1", "status": {"$ne": "failed"}}
    )
    mock_cursor.sort.assert_called_once_with("created_at", 1)


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_get_run_documents_returns_empty_on_error(mock_get_db):
    """get_run_documents should return [] on database errors."""
    mock_collection = MagicMock()
    mock_collection.find.side_effect = ServerSelectionTimeoutError("timeout")

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = get_run_documents("run-1")
    assert result == []


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_get_run_documents_empty_result(mock_get_db):
    """get_run_documents should handle empty result set."""
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = []

    mock_collection = MagicMock()
    mock_collection.find.return_value = mock_cursor

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = get_run_documents("run-nonexistent")
    assert result == []


# ── mark_completed ──────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_mark_completed_updates_documents(mock_get_db):
    """mark_completed should set status=completed on all docs for the run_id."""
    mock_collection = MagicMock()
    mock_collection.update_many.return_value = MagicMock(modified_count=5)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    count = mark_completed("run-abc")

    assert count == 5
    mock_db.__getitem__.assert_called_with(WORKING_COLLECTION)
    mock_collection.update_many.assert_called_once()
    call_args = mock_collection.update_many.call_args
    assert call_args[0][0] == {"run_id": "run-abc"}
    update_set = call_args[0][1]["$set"]
    assert update_set["status"] == "completed"
    assert "completed_at" in update_set


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_mark_completed_returns_zero_on_db_error(mock_get_db):
    """mark_completed should catch PyMongo errors and return 0."""
    mock_collection = MagicMock()
    mock_collection.update_many.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    count = mark_completed("run-abc")
    assert count == 0


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_mark_completed_returns_zero_when_no_docs(mock_get_db):
    """mark_completed should return 0 when run_id has no documents."""
    mock_collection = MagicMock()
    mock_collection.update_many.return_value = MagicMock(modified_count=0)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    count = mark_completed("run-nonexistent")
    assert count == 0


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_find_unfinalized_excludes_completed_runs(mock_get_db):
    """find_unfinalized should exclude run_ids that have status=completed."""
    mock_finalized_col = MagicMock()
    mock_finalized_col.distinct.return_value = []  # nothing in finalizeIdeas

    mock_working_col = MagicMock()
    mock_working_col.distinct.return_value = ["run-done"]  # marked completed
    mock_working_col.aggregate.return_value = []  # all excluded

    def getitem(name):
        if name == "finalizeIdeas":
            return mock_finalized_col
        return mock_working_col

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=getitem)
    mock_get_db.return_value = mock_db

    runs = find_unfinalized()
    assert runs == []
    # Verify both exclusion sources were queried
    mock_working_col.distinct.assert_called_once_with("run_id", {"status": "completed"})
