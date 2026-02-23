"""Tests for mongodb.working_ideas.repository — save_iteration, save_pipeline_step, save_failed, update_section_critique, find_unfinalized, get_run_documents, mark_completed."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from crewai_productfeature_planner.mongodb.working_ideas.repository import (
    WORKING_COLLECTION,
    ensure_section_field,
    find_completed_without_confluence,
    find_completed_without_output,
    find_unfinalized,
    get_output_file,
    get_run_documents,
    mark_completed,
    mark_paused,
    save_confluence_url,
    save_executive_summary,
    save_failed,
    save_finalized_idea,
    save_iteration,
    save_output_file,
    save_pipeline_step,
    update_executive_summary_critique,
    update_section_critique,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── save_iteration ────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_iteration_upserts_doc(mock_get_db):
    """save_iteration should upsert into workingIdeas with $push."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(upserted_id="abc123")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = save_iteration(
        run_id="run-1", idea="Dark mode", iteration=2, draft={"executive_summary": "# Draft v2"}
    )

    mock_db.__getitem__.assert_called_with(WORKING_COLLECTION)
    mock_collection.update_one.assert_called_once()
    call_args = mock_collection.update_one.call_args
    # Filter is by run_id
    assert call_args[0][0] == {"run_id": "run-1"}
    # Should use upsert=True
    assert call_args[1].get("upsert") is True
    update_ops = call_args[0][1]
    assert update_ops["$set"]["idea"] == "Dark mode"
    assert update_ops["$set"]["status"] == "inprogress"
    assert "$push" in update_ops
    assert "section.executive_summary" in update_ops["$push"]
    pushed = update_ops["$push"]["section.executive_summary"]
    assert pushed["content"] == "# Draft v2"
    assert pushed["iteration"] == 2
    assert result == "abc123"


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_iteration_includes_critique(mock_get_db):
    """Critique field should be saved in the pushed iteration record."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(upserted_id=None)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    save_iteration(
        run_id="r1", idea="X", iteration=1, draft={"exec": "D"}, critique="Needs work"
    )

    call_args = mock_collection.update_one.call_args
    update_ops = call_args[0][1]
    pushed = update_ops["$push"]["section.exec"]
    assert pushed["critique"] == "Needs work"


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_iteration_no_step_field(mock_get_db):
    """Iteration records should not include a 'step' field (matches YAML schema)."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(upserted_id=None)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    save_iteration(
        run_id="r1", idea="X", iteration=1, draft={"exec": "D"}, step="critique"
    )

    call_args = mock_collection.update_one.call_args
    update_ops = call_args[0][1]
    pushed = update_ops["$push"]["section.exec"]
    assert "step" not in pushed
    assert set(pushed.keys()) == {"content", "iteration", "critique", "updated_date"}


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_iteration_returns_none_on_db_error(mock_get_db):
    """save_iteration should catch PyMongo errors and return None."""
    mock_collection = MagicMock()
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError(
        "connection refused"
    )
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = save_iteration(
        run_id="r1", idea="X", iteration=1, draft={"exec": "D"}
    )
    assert result is None


# ── save_pipeline_step ──────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_pipeline_step_upserts_under_pipeline(mock_get_db):
    """save_pipeline_step should store data under pipeline.*, not section.*."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(upserted_id="pipe1")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = save_pipeline_step(
        run_id="run-1",
        idea="Test idea",
        pipeline_key="requirements_breakdown",
        iteration=1,
        content="Breakdown v1",
        critique="Needs more detail",
        step="requirements_breakdown_1",
    )

    mock_collection.update_one.assert_called_once()
    call_args = mock_collection.update_one.call_args
    assert call_args[0][0] == {"run_id": "run-1"}
    assert call_args[1].get("upsert") is True
    update_ops = call_args[0][1]
    # Data goes under top-level requirements_breakdown, NOT pipeline.*
    assert "$push" in update_ops
    assert "requirements_breakdown" in update_ops["$push"]
    assert "pipeline.requirements_breakdown" not in update_ops.get("$push", {})
    pushed = update_ops["$push"]["requirements_breakdown"]
    assert pushed["content"] == "Breakdown v1"
    assert pushed["iteration"] == 1
    assert pushed["critique"] == "Needs more detail"
    assert pushed["step"] == "requirements_breakdown_1"
    assert result == "pipe1"


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_pipeline_step_returns_none_on_error(mock_get_db):
    """save_pipeline_step should catch PyMongo errors and return None."""
    mock_collection = MagicMock()
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = save_pipeline_step(
        run_id="run-1", idea="X", pipeline_key="requirements_breakdown",
        iteration=1, content="data",
    )
    assert result is None


# ── save_failed ─────────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_failed_upserts_doc(mock_get_db):
    """save_failed should upsert a failure record into workingIdeas."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(upserted_id="fail123")
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
    # Two update_one calls: 1) ensure section exists, 2) upsert failure record
    assert mock_collection.update_one.call_count == 2
    # First call: ensure section field exists
    init_call = mock_collection.update_one.call_args_list[0]
    assert init_call[0][0] == {"run_id": "run-x", "section": {"$exists": False}}
    assert init_call[0][1] == {"$set": {"section": {}}}
    # Second call: the actual failure upsert
    call_args = mock_collection.update_one.call_args_list[1]
    assert call_args[0][0] == {"run_id": "run-x"}
    assert call_args[1].get("upsert") is True
    update_ops = call_args[0][1]
    assert update_ops["$set"]["status"] == "failed"
    assert update_ops["$set"]["error"] == "LLM timeout"
    assert result == "fail123"


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_failed_returns_none_on_db_error(mock_get_db):
    """save_failed should catch PyMongo errors and return None."""
    mock_collection = MagicMock()
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError(
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
    mock_collection.update_one.return_value = MagicMock(upserted_id="f1")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    save_failed(run_id="r1", idea="X", iteration=1, error="err")

    call_args = mock_collection.update_one.call_args
    update_ops = call_args[0][1]
    assert update_ops["$set"]["status"] == "failed"


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_failed_sets_error_field(mock_get_db):
    """save_failed should set the error field in the update."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(upserted_id="f2")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    save_failed(
        run_id="r2", idea="Y", iteration=3, error="quota",
        step="draft_edge_cases",
    )

    call_args = mock_collection.update_one.call_args
    update_ops = call_args[0][1]
    assert update_ops["$set"]["error"] == "quota"


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_failed_initializes_section_on_existing_doc(mock_get_db):
    """save_failed should ensure section field exists on pre-existing documents."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(upserted_id=None)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    save_failed(run_id="run-existing", idea="X", iteration=1, error="err")

    # First call ensures section field exists
    init_args = mock_collection.update_one.call_args_list[0]
    assert init_args[0][0] == {
        "run_id": "run-existing",
        "section": {"$exists": False},
    }
    assert init_args[0][1] == {"$set": {"section": {}}}


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_failed_setOnInsert_includes_section(mock_get_db):
    """save_failed $setOnInsert should include section: {} for new documents."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(upserted_id="new")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    save_failed(run_id="run-new", idea="X", iteration=1, error="err")

    # Second call is the upsert — check $setOnInsert includes section
    upsert_args = mock_collection.update_one.call_args_list[1]
    update_ops = upsert_args[0][1]
    assert "$setOnInsert" in update_ops
    assert update_ops["$setOnInsert"]["section"] == {}


# ── save_executive_summary — section initialization ────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_executive_summary_setOnInsert_includes_section(mock_get_db):
    """save_executive_summary $setOnInsert should include section: {} for new documents."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(upserted_id="es-new")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    save_executive_summary(
        run_id="run-init", idea="X", iteration=1, content="summary",
    )

    ops = mock_collection.update_one.call_args[0][1]
    assert "$setOnInsert" in ops
    assert ops["$setOnInsert"]["section"] == {}


# ── save_pipeline_step — section initialization ────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_pipeline_step_setOnInsert_includes_section(mock_get_db):
    """save_pipeline_step $setOnInsert should include section: {} for new documents."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(upserted_id="ps-new")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    save_pipeline_step(
        run_id="run-init", idea="X", pipeline_key="requirements_breakdown",
        iteration=1, content="breakdown",
    )

    ops = mock_collection.update_one.call_args[0][1]
    assert "$setOnInsert" in ops
    assert ops["$setOnInsert"]["section"] == {}


# ── update_section_critique ─────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_update_section_critique_updates_record(mock_get_db):
    """update_section_critique should $set critique on the matching iteration record."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = update_section_critique(
        run_id="run-1",
        section_key="executive_summary",
        iteration=1,
        critique="Needs more detail on user impact",
    )

    assert result is True
    mock_collection.update_one.assert_called_once()
    call_args = mock_collection.update_one.call_args
    # Filter matches run_id + array element with matching iteration
    filt = call_args[0][0]
    assert filt["run_id"] == "run-1"
    assert filt["section.executive_summary.iteration"] == 1
    # $set uses positional operator to update matched element
    update_set = call_args[0][1]["$set"]
    assert update_set["section.executive_summary.$.critique"] == "Needs more detail on user impact"
    assert "section.executive_summary.$.updated_date" in update_set
    assert "update_date" in update_set


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_update_section_critique_returns_false_when_no_match(mock_get_db):
    """update_section_critique should return False when no record matches."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(modified_count=0)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = update_section_critique(
        run_id="run-1",
        section_key="executive_summary",
        iteration=99,
        critique="Some critique",
    )

    assert result is False


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_update_section_critique_returns_false_on_error(mock_get_db):
    """update_section_critique should catch PyMongo errors and return False."""
    mock_collection = MagicMock()
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = update_section_critique(
        run_id="run-1",
        section_key="executive_summary",
        iteration=1,
        critique="Some critique",
    )

    assert result is False


# ── find_unfinalized ────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_find_unfinalized_returns_runs(mock_get_db):
    """find_unfinalized should return run summaries with non-completed status."""
    ts = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
    working_docs = [
        {
            "run_id": "run-abc",
            "idea": "Dark mode",
            "created_at": ts,
            "status": "inprogress",
            "section": {
                "executive_summary": [{"content": "...", "iteration": 3, "critique": "", "updated_date": ""}],
                "problem_statement": [{"content": "...", "iteration": 1, "critique": "", "updated_date": ""}],
            },
        }
    ]

    mock_collection = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = working_docs
    mock_collection.find.return_value = mock_cursor

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    runs = find_unfinalized()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run-abc"
    assert runs[0]["idea"] == "Dark mode"
    assert runs[0]["iteration"] == 3
    assert "executive_summary" in runs[0]["sections"]
    assert "problem_statement" in runs[0]["sections"]
    assert runs[0]["exec_summary_iterations"] == 0  # no top-level array
    assert runs[0]["req_breakdown_iterations"] == 0  # no top-level array


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_find_unfinalized_empty_when_all_completed(mock_get_db):
    """find_unfinalized should return empty if every run is completed."""
    mock_collection = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = []
    mock_collection.find.return_value = mock_cursor

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    runs = find_unfinalized()
    assert runs == []


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_find_unfinalized_returns_empty_on_error(mock_get_db):
    """find_unfinalized should return [] on database errors."""
    mock_get_db.side_effect = ServerSelectionTimeoutError("timeout")
    assert find_unfinalized() == []


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_find_unfinalized_skips_empty_draft_sections(mock_get_db):
    """find_unfinalized should only report sections with iteration data."""
    working_docs = [
        {
            "run_id": "run-1",
            "idea": "Test",
            "created_at": None,
            "status": "inprogress",
            "section": {
                "executive_summary": [{"content": "...", "iteration": 1, "critique": "", "updated_date": ""}],
                "problem_statement": [],  # empty array — not started
            },
        }
    ]

    mock_collection = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = working_docs
    mock_collection.find.return_value = mock_cursor

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    runs = find_unfinalized()
    assert runs[0]["sections"] == ["executive_summary"]


# ── get_run_documents ───────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_get_run_documents_returns_doc(mock_get_db):
    """get_run_documents should return the single doc for a run as a list."""
    doc = {
        "run_id": "run-1",
        "idea": "Test",
        "section": {
            "executive_summary": [{"content": "...", "iteration": 1, "critique": "", "updated_date": ""}],
        },
        "status": "inprogress",
    }
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = doc

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = get_run_documents("run-1")
    assert result == [doc]
    mock_collection.find_one.assert_called_once_with(
        {"run_id": "run-1", "status": {"$ne": "completed"}}
    )


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_get_run_documents_returns_empty_on_error(mock_get_db):
    """get_run_documents should return [] on database errors."""
    mock_collection = MagicMock()
    mock_collection.find_one.side_effect = ServerSelectionTimeoutError("timeout")

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = get_run_documents("run-1")
    assert result == []


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_get_run_documents_empty_result(mock_get_db):
    """get_run_documents should handle not-found result."""
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = None

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = get_run_documents("run-nonexistent")
    assert result == []


# ── mark_completed ──────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_mark_completed_updates_document(mock_get_db):
    """mark_completed should set status=completed on the doc for the run_id."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    count = mark_completed("run-abc")

    assert count == 1
    mock_db.__getitem__.assert_called_with(WORKING_COLLECTION)
    mock_collection.update_one.assert_called_once()
    call_args = mock_collection.update_one.call_args
    assert call_args[0][0] == {"run_id": "run-abc"}
    update_set = call_args[0][1]["$set"]
    assert update_set["status"] == "completed"
    assert "completed_at" in update_set
    assert "update_date" in update_set


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_mark_completed_returns_zero_on_db_error(mock_get_db):
    """mark_completed should catch PyMongo errors and return 0."""
    mock_collection = MagicMock()
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    count = mark_completed("run-abc")
    assert count == 0


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_mark_completed_returns_zero_when_no_docs(mock_get_db):
    """mark_completed should return 0 when run_id has no documents."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(modified_count=0)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    count = mark_completed("run-nonexistent")
    assert count == 0


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_find_unfinalized_excludes_completed_runs(mock_get_db):
    """find_unfinalized should exclude documents with status=completed but include failed."""
    mock_collection = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = []  # all excluded by query filter
    mock_collection.find.return_value = mock_cursor

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    runs = find_unfinalized()
    assert runs == []
    # Verify the query filters out completed only (failed is resumable)
    find_call = mock_collection.find.call_args
    query = find_call[0][0]
    assert "completed" in query["status"]["$nin"]
    assert "failed" not in query["status"]["$nin"]


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_find_unfinalized_counts_exec_summary_array(mock_get_db):
    """find_unfinalized should count top-level executive_summary iterations."""
    working_docs = [
        {
            "run_id": "run-exec",
            "idea": "AI chat",
            "created_at": None,
            "status": "inprogress",
            "section": {},  # no draft sections yet
            "executive_summary": [
                {"content": "v1", "iteration": 1},
                {"content": "v2", "iteration": 2},
                {"content": "v3", "iteration": 3},
                {"content": "v4", "iteration": 4},
            ],
        }
    ]

    mock_collection = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = working_docs
    mock_collection.find.return_value = mock_cursor

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    runs = find_unfinalized()
    assert runs[0]["exec_summary_iterations"] == 4
    # effective iteration should be max(draft=0, exec=4)
    assert runs[0]["iteration"] == 4
    assert runs[0]["sections"] == []  # no draft sections
    assert runs[0]["req_breakdown_iterations"] == 0  # no requirements_breakdown array


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_find_unfinalized_counts_req_breakdown_array(mock_get_db):
    """find_unfinalized should count top-level requirements_breakdown iterations."""
    working_docs = [
        {
            "run_id": "run-rb",
            "idea": "Smart search",
            "created_at": None,
            "status": "inprogress",
            "section": {},
            "executive_summary": [
                {"content": "v1", "iteration": 1},
            ],
            "requirements_breakdown": [
                {"content": "reqs v1", "iteration": 1, "critique": "needs work"},
                {"content": "reqs v2", "iteration": 2, "critique": "better"},
                {"content": "reqs v3", "iteration": 3, "critique": "READY_FOR_DEV"},
            ],
        }
    ]

    mock_collection = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = working_docs
    mock_collection.find.return_value = mock_cursor

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    runs = find_unfinalized()
    assert runs[0]["req_breakdown_iterations"] == 3
    assert runs[0]["exec_summary_iterations"] == 1


# ── save_executive_summary ──────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_executive_summary_upserts(mock_get_db):
    """save_executive_summary should push to top-level executive_summary array."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(upserted_id=None)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = save_executive_summary(
        run_id="run-es-1",
        idea="Test idea",
        iteration=1,
        content="Executive summary content",
        critique=None,
    )

    assert result == "run-es-1"
    mock_collection.update_one.assert_called_once()
    call_args = mock_collection.update_one.call_args
    assert call_args[0][0] == {"run_id": "run-es-1"}
    ops = call_args[0][1]
    assert "$push" in ops
    assert "executive_summary" in ops["$push"]
    record = ops["$push"]["executive_summary"]
    assert record["content"] == "Executive summary content"
    assert record["iteration"] == 1
    assert record["critique"] is None
    assert "updated_date" in record
    assert ops["$set"]["status"] == "inprogress"
    assert call_args[1]["upsert"] is True


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_executive_summary_with_critique(mock_get_db):
    """save_executive_summary should store critique when provided."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(upserted_id=None)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    save_executive_summary(
        run_id="run-es-2",
        idea="Test idea",
        iteration=2,
        content="Refined summary",
        critique="Needs more detail",
    )

    record = mock_collection.update_one.call_args[0][1]["$push"]["executive_summary"]
    assert record["critique"] == "Needs more detail"
    assert record["iteration"] == 2


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_executive_summary_returns_none_on_error(mock_get_db):
    """save_executive_summary should return None on PyMongo error."""
    mock_collection = MagicMock()
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = save_executive_summary(
        run_id="run-err",
        idea="Test",
        iteration=1,
        content="content",
    )
    assert result is None


# ── update_executive_summary_critique ───────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_update_executive_summary_critique_updates_record(mock_get_db):
    """update_executive_summary_critique should update critique on matching iteration."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = update_executive_summary_critique(
        run_id="run-crit",
        iteration=2,
        critique="READY_FOR_DEV — looks great",
    )

    assert result is True
    call_args = mock_collection.update_one.call_args
    query = call_args[0][0]
    assert query["run_id"] == "run-crit"
    assert query["executive_summary.iteration"] == 2
    update = call_args[0][1]["$set"]
    assert update["executive_summary.$.critique"] == "READY_FOR_DEV — looks great"
    assert "executive_summary.$.updated_date" in update
    assert "update_date" in update


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_update_executive_summary_critique_returns_false_on_error(mock_get_db):
    """update_executive_summary_critique should return False on PyMongo error."""
    mock_collection = MagicMock()
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = update_executive_summary_critique(
        run_id="run-err",
        iteration=1,
        critique="critique text",
    )
    assert result is False


# ── save_finalized_idea ─────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_finalized_idea_updates_doc(mock_get_db):
    """save_finalized_idea should $set finalized_idea on the document."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = save_finalized_idea(
        run_id="run-fin",
        finalized_idea="The final exec summary content",
    )

    assert result is True
    call_args = mock_collection.update_one.call_args
    assert call_args[0][0] == {"run_id": "run-fin"}
    update_set = call_args[0][1]["$set"]
    assert update_set["finalized_idea"] == "The final exec summary content"
    assert "update_date" in update_set


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_finalized_idea_returns_false_on_error(mock_get_db):
    """save_finalized_idea should catch PyMongo errors and return False."""
    mock_collection = MagicMock()
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = save_finalized_idea(
        run_id="run-err",
        finalized_idea="content",
    )
    assert result is False


# ── save_output_file ──────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_output_file_updates_doc(mock_get_db):
    """save_output_file should $set output_file on the document."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = save_output_file(
        run_id="run-out",
        output_file="output/prds/2026/02/prd_v10_20260223_071542.md",
    )

    assert result is True
    call_args = mock_collection.update_one.call_args
    assert call_args[0][0] == {"run_id": "run-out"}
    update_set = call_args[0][1]["$set"]
    assert update_set["output_file"] == "output/prds/2026/02/prd_v10_20260223_071542.md"
    assert "update_date" in update_set


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_output_file_returns_false_on_error(mock_get_db):
    """save_output_file should catch PyMongo errors and return False."""
    mock_collection = MagicMock()
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = save_output_file(run_id="run-err", output_file="some/path.md")
    assert result is False


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_save_output_file_returns_false_when_no_match(mock_get_db):
    """save_output_file should return False when no document matches."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(modified_count=0)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = save_output_file(run_id="nonexistent", output_file="path.md")
    assert result is False


# ── find_completed_without_output ─────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_find_completed_without_output_returns_docs(mock_get_db):
    """Should return completed docs that have no output_file."""
    docs = [
        {"run_id": "run-1", "status": "completed", "idea": "Idea 1"},
        {"run_id": "run-2", "status": "completed", "idea": "Idea 2"},
    ]
    mock_collection = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = docs
    mock_collection.find.return_value = mock_cursor
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = find_completed_without_output()

    assert len(result) == 2
    assert result[0]["run_id"] == "run-1"
    # Verify the query uses $or for missing/null/empty output_file
    call_args = mock_collection.find.call_args
    query = call_args[0][0]
    assert query["status"] == "completed"
    assert "$or" in query


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_find_completed_without_output_returns_empty(mock_get_db):
    """Should return empty list when all completed docs have output_file."""
    mock_collection = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = []
    mock_collection.find.return_value = mock_cursor
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = find_completed_without_output()
    assert result == []


# ── get_output_file ───────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_get_output_file_returns_path(mock_get_db):
    """Should return the output_file value from the document."""
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = {
        "output_file": "output/prds/2026/02/prd_v1.md",
    }
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = get_output_file("run-1")

    assert result == "output/prds/2026/02/prd_v1.md"
    mock_collection.find_one.assert_called_once_with(
        {"run_id": "run-1"},
        {"output_file": 1, "_id": 0},
    )


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_get_output_file_returns_none_when_missing(mock_get_db):
    """Should return None when document has no output_file."""
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = {}
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    assert get_output_file("run-1") is None


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_get_output_file_returns_none_when_empty_string(mock_get_db):
    """Should return None when output_file is empty string."""
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = {"output_file": ""}
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    assert get_output_file("run-1") is None


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_get_output_file_returns_none_when_no_doc(mock_get_db):
    """Should return None when document is not found."""
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = None
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    assert get_output_file("run-1") is None


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_get_output_file_returns_none_on_error(mock_get_db):
    """Should return None on database error."""
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(
        side_effect=ServerSelectionTimeoutError("timeout"),
    )
    mock_get_db.return_value = mock_db

    assert get_output_file("run-1") is None


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_find_completed_without_output_returns_empty_on_error(mock_get_db):
    """Should return empty list on database error."""
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(
        side_effect=ServerSelectionTimeoutError("timeout"),
    )
    mock_get_db.return_value = mock_db

    result = find_completed_without_output()
    assert result == []


# ── mark_paused ───────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_mark_paused_updates_status(mock_get_db):
    """mark_paused should set status=paused on the document."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = mark_paused("run-1")

    assert result == 1
    call_args = mock_collection.update_one.call_args
    query = call_args[0][0]
    update = call_args[0][1]
    assert query == {"run_id": "run-1"}
    assert update["$set"]["status"] == "paused"
    assert "update_date" in update["$set"]


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_mark_paused_returns_zero_when_no_match(mock_get_db):
    """mark_paused should return 0 when no document matches."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(modified_count=0)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    assert mark_paused("nonexistent") == 0


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_mark_paused_returns_zero_on_error(mock_get_db):
    """mark_paused should return 0 on database error."""
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(
        side_effect=ServerSelectionTimeoutError("timeout"),
    )
    mock_get_db.return_value = mock_db

    assert mark_paused("run-1") == 0


# ── ensure_section_field ──────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_ensure_section_field_creates_missing(mock_get_db):
    """ensure_section_field should create section={} when field is missing."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = ensure_section_field("run-1")

    assert result is True
    call_args = mock_collection.update_one.call_args
    assert call_args[0][0] == {"run_id": "run-1", "section": {"$exists": False}}
    assert call_args[0][1] == {"$set": {"section": {}}}


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_ensure_section_field_noop_when_exists(mock_get_db):
    """ensure_section_field should return False when section already exists."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(modified_count=0)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = ensure_section_field("run-1")

    assert result is False


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_ensure_section_field_returns_false_on_error(mock_get_db):
    """ensure_section_field should return False on database error."""
    mock_collection = MagicMock()
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = ensure_section_field("run-1")

    assert result is False


# ── find_unfinalized — section_missing flag ───────────────────


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_find_unfinalized_flags_section_missing(mock_get_db):
    """find_unfinalized should set section_missing=True when section field absent."""
    ts = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
    # Document WITHOUT a 'section' field at all
    working_docs = [
        {
            "run_id": "run-no-sec",
            "idea": "idea without section",
            "created_at": ts,
            "status": "paused",
            "executive_summary": [{"content": "exec", "iteration": 1}],
        }
    ]

    mock_collection = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = working_docs
    mock_collection.find.return_value = mock_cursor
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    runs = find_unfinalized()
    assert len(runs) == 1
    assert runs[0]["section_missing"] is True


@patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
def test_find_unfinalized_section_not_missing_when_present(mock_get_db):
    """find_unfinalized should set section_missing=False when section field exists."""
    ts = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
    working_docs = [
        {
            "run_id": "run-with-sec",
            "idea": "idea with section",
            "created_at": ts,
            "status": "inprogress",
            "section": {"problem_statement": [{"content": "x", "iteration": 1}]},
        }
    ]

    mock_collection = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = working_docs
    mock_collection.find.return_value = mock_cursor
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    runs = find_unfinalized()
    assert len(runs) == 1
    assert runs[0]["section_missing"] is False


# ── save_confluence_url ───────────────────────────────────────


class TestSaveConfluenceUrl:

    @patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
    def test_updates_document(self, mock_get_db):
        mock_collection = MagicMock()
        mock_collection.update_one.return_value = MagicMock(modified_count=1)
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_get_db.return_value = mock_db

        result = save_confluence_url(
            run_id="run-1",
            confluence_url="https://example.atlassian.net/wiki/pages/123",
            page_id="123",
        )

        assert result is True
        mock_collection.update_one.assert_called_once()
        call_args = mock_collection.update_one.call_args
        assert call_args[0][0] == {"run_id": "run-1"}
        set_fields = call_args[0][1]["$set"]
        assert set_fields["confluence_url"] == "https://example.atlassian.net/wiki/pages/123"
        assert set_fields["confluence_page_id"] == "123"
        assert "confluence_published_at" in set_fields

    @patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
    def test_no_page_id(self, mock_get_db):
        mock_collection = MagicMock()
        mock_collection.update_one.return_value = MagicMock(modified_count=1)
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_get_db.return_value = mock_db

        save_confluence_url(
            run_id="r2",
            confluence_url="https://example.atlassian.net/wiki/pages/456",
        )

        set_fields = mock_collection.update_one.call_args[0][1]["$set"]
        assert "confluence_page_id" not in set_fields

    @patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
    def test_returns_false_on_no_match(self, mock_get_db):
        mock_collection = MagicMock()
        mock_collection.update_one.return_value = MagicMock(modified_count=0)
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_get_db.return_value = mock_db

        result = save_confluence_url(
            run_id="unknown-run",
            confluence_url="https://example.atlassian.net/wiki/pages/000",
        )
        assert result is False

    @patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
    def test_returns_false_on_db_error(self, mock_get_db):
        from pymongo.errors import PyMongoError
        mock_get_db.side_effect = PyMongoError("connection failed")

        result = save_confluence_url(
            run_id="run-1",
            confluence_url="https://example.atlassian.net/wiki/pages/123",
        )
        assert result is False


# ── find_completed_without_confluence ────────────────────────────────


class TestFindCompletedWithoutConfluence:

    @patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
    def test_returns_matching_docs(self, mock_get_db):
        docs = [
            {"run_id": "r1", "status": "completed", "idea": "idea1"},
            {"run_id": "r2", "status": "completed", "idea": "idea2"},
        ]
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = docs
        mock_collection = MagicMock()
        mock_collection.find.return_value = mock_cursor
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_get_db.return_value = mock_db

        result = find_completed_without_confluence()

        assert len(result) == 2
        assert result[0]["run_id"] == "r1"
        # Verify query has correct structure
        query = mock_collection.find.call_args[0][0]
        assert query["status"] == "completed"
        assert "$or" in query

    @patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
    def test_returns_empty_on_no_results(self, mock_get_db):
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = []
        mock_collection = MagicMock()
        mock_collection.find.return_value = mock_cursor
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_get_db.return_value = mock_db

        result = find_completed_without_confluence()
        assert result == []

    @patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
    def test_returns_empty_on_db_error(self, mock_get_db):
        from pymongo.errors import PyMongoError
        mock_get_db.side_effect = PyMongoError("connection failed")

        result = find_completed_without_confluence()
        assert result == []
