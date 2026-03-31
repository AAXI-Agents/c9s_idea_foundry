"""Tests for mongodb.working_ideas.repository — save_iteration, save_pipeline_step, save_failed, update_section_critique, find_unfinalized, get_run_documents, mark_completed."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from crewai_productfeature_planner.mongodb.working_ideas.repository import (
    WORKING_COLLECTION,
    ensure_section_field,
    fail_unfinalized_on_startup,
    find_completed_without_confluence,
    find_completed_without_output,
    find_ideas_by_project,
    find_unfinalized,
    get_output_file,
    get_run_documents,
    mark_archived,
    mark_completed,
    mark_paused,
    save_executive_summary,
    save_failed,
    save_finalized_idea,
    save_iteration,
    save_jira_phase,
    save_output_file,
    save_pipeline_step,
    save_project_ref,
    save_slack_context,
    update_executive_summary_critique,
    update_section_critique,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── save_iteration ────────────────────────────────────────────


def test_save_iteration_upserts_doc(wi_mocks):
    """save_iteration should upsert into workingIdeas with $push."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id="abc123")

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
    # idea is in $set so it is always written (even on existing docs)
    assert update_ops["$set"]["idea"] == "Dark mode"
    assert update_ops["$set"]["status"] == "inprogress"
    assert "$push" in update_ops
    assert "section.executive_summary" in update_ops["$push"]
    pushed = update_ops["$push"]["section.executive_summary"]
    assert pushed["content"] == "# Draft v2"
    assert pushed["iteration"] == 2
    assert result == "abc123"


def test_save_iteration_includes_critique(wi_mocks):
    """Critique field should be saved in the pushed iteration record."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id=None)

    save_iteration(
        run_id="r1", idea="X", iteration=1, draft={"exec": "D"}, critique="Needs work"
    )

    call_args = mock_collection.update_one.call_args
    update_ops = call_args[0][1]
    pushed = update_ops["$push"]["section.exec"]
    assert pushed["critique"] == "Needs work"


def test_save_iteration_no_step_field(wi_mocks):
    """Iteration records should not include a 'step' field (matches YAML schema)."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id=None)

    save_iteration(
        run_id="r1", idea="X", iteration=1, draft={"exec": "D"}, step="critique"
    )

    call_args = mock_collection.update_one.call_args
    update_ops = call_args[0][1]
    pushed = update_ops["$push"]["section.exec"]
    assert "step" not in pushed
    assert set(pushed.keys()) == {"content", "iteration", "critique", "updated_date"}


def test_save_iteration_idea_in_set(wi_mocks):
    """idea should be in $set so it is always written (even on existing docs)."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id=None)

    save_iteration(run_id="r1", idea="Original idea", iteration=1, draft={"s": "D"})

    update_ops = mock_collection.update_one.call_args[0][1]
    assert update_ops["$set"]["idea"] == "Original idea"
    assert "idea" not in update_ops["$setOnInsert"]


def test_save_iteration_finalized_idea_in_set(wi_mocks):
    """finalized_idea should be written to $set when provided."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id=None)

    save_iteration(
        run_id="r1", idea="Original", iteration=1,
        draft={"s": "D"}, finalized_idea="Refined version",
    )

    update_ops = mock_collection.update_one.call_args[0][1]
    assert update_ops["$set"]["finalized_idea"] == "Refined version"


def test_save_iteration_no_finalized_idea_omits_field(wi_mocks):
    """When finalized_idea is empty, it should NOT appear in $set."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id=None)

    save_iteration(run_id="r1", idea="X", iteration=1, draft={"s": "D"})

    update_ops = mock_collection.update_one.call_args[0][1]
    assert "finalized_idea" not in update_ops["$set"]


def test_save_iteration_returns_none_on_db_error(wi_mocks):
    """save_iteration should catch PyMongo errors and return None."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError(
        "connection refused"
    )

    result = save_iteration(
        run_id="r1", idea="X", iteration=1, draft={"exec": "D"}
    )
    assert result is None


# ── save_pipeline_step ──────────────────────────────────────────


def test_save_pipeline_step_upserts_under_pipeline(wi_mocks):
    """save_pipeline_step should store data under pipeline.*, not section.*."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id="pipe1")

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


def test_save_pipeline_step_returns_none_on_error(wi_mocks):
    """save_pipeline_step should catch PyMongo errors and return None."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("timeout")

    result = save_pipeline_step(
        run_id="run-1", idea="X", pipeline_key="requirements_breakdown",
        iteration=1, content="data",
    )
    assert result is None


# ── save_failed ─────────────────────────────────────────────────


def test_save_failed_upserts_doc(wi_mocks):
    """save_failed should upsert a failure record into workingIdeas."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id="fail123")

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


def test_save_failed_returns_none_on_db_error(wi_mocks):
    """save_failed should catch PyMongo errors and return None."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError(
        "connection refused"
    )

    result = save_failed(
        run_id="r1", idea="X", iteration=1, error="boom"
    )
    assert result is None


def test_save_failed_minimal_fields(wi_mocks):
    """save_failed with only required fields should use empty defaults."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id="f1")

    save_failed(run_id="r1", idea="X", iteration=1, error="err")

    call_args = mock_collection.update_one.call_args
    update_ops = call_args[0][1]
    assert update_ops["$set"]["status"] == "failed"


def test_save_failed_sets_error_field(wi_mocks):
    """save_failed should set the error field in the update."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id="f2")

    save_failed(
        run_id="r2", idea="Y", iteration=3, error="quota",
        step="draft_edge_cases",
    )

    call_args = mock_collection.update_one.call_args
    update_ops = call_args[0][1]
    assert update_ops["$set"]["error"] == "quota"


def test_save_failed_initializes_section_on_existing_doc(wi_mocks):
    """save_failed should ensure section field exists on pre-existing documents."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id=None)

    save_failed(run_id="run-existing", idea="X", iteration=1, error="err")

    # First call ensures section field exists
    init_args = mock_collection.update_one.call_args_list[0]
    assert init_args[0][0] == {
        "run_id": "run-existing",
        "section": {"$exists": False},
    }
    assert init_args[0][1] == {"$set": {"section": {}}}


def test_save_failed_setOnInsert_includes_section(wi_mocks):
    """save_failed $setOnInsert should include section: {} for new documents."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id="new")

    save_failed(run_id="run-new", idea="X", iteration=1, error="err")

    # Second call is the upsert — check $setOnInsert includes section
    upsert_args = mock_collection.update_one.call_args_list[1]
    update_ops = upsert_args[0][1]
    assert "$setOnInsert" in update_ops
    assert update_ops["$setOnInsert"]["section"] == {}


def test_save_failed_idea_in_setOnInsert(wi_mocks):
    """save_failed should store idea in $setOnInsert, not $set."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id="new")

    save_failed(run_id="run-f", idea="My original idea", iteration=1, error="err")

    upsert_args = mock_collection.update_one.call_args_list[1]
    update_ops = upsert_args[0][1]
    assert "idea" not in update_ops["$set"]
    assert update_ops["$setOnInsert"]["idea"] == "My original idea"


# ── save_executive_summary — section initialization ────────────


def test_save_executive_summary_setOnInsert_includes_section(wi_mocks):
    """save_executive_summary $setOnInsert should include section: {} for new documents."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id="es-new")

    save_executive_summary(
        run_id="run-init", idea="X", iteration=1, content="summary",
    )

    ops = mock_collection.update_one.call_args[0][1]
    assert "$setOnInsert" in ops
    assert ops["$setOnInsert"]["section"] == {}


def test_save_executive_summary_idea_in_setOnInsert(wi_mocks):
    """save_executive_summary should store idea in $setOnInsert, not $set."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id="es-x")

    save_executive_summary(
        run_id="run-es", idea="Original user input", iteration=1, content="content",
    )

    ops = mock_collection.update_one.call_args[0][1]
    assert "idea" not in ops["$set"]
    assert ops["$setOnInsert"]["idea"] == "Original user input"


# ── save_pipeline_step — section initialization ────────────────


def test_save_pipeline_step_setOnInsert_includes_section(wi_mocks):
    """save_pipeline_step $setOnInsert should include section: {} for new documents."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id="ps-new")

    save_pipeline_step(
        run_id="run-init", idea="X", pipeline_key="requirements_breakdown",
        iteration=1, content="breakdown",
    )

    ops = mock_collection.update_one.call_args[0][1]
    assert "$setOnInsert" in ops
    assert ops["$setOnInsert"]["section"] == {}


def test_save_pipeline_step_idea_in_setOnInsert(wi_mocks):
    """save_pipeline_step should store idea in $setOnInsert, not $set."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id="ps-x")

    save_pipeline_step(
        run_id="run-ps", idea="User original", pipeline_key="req",
        iteration=1, content="c",
    )

    ops = mock_collection.update_one.call_args[0][1]
    assert "idea" not in ops["$set"]
    assert ops["$setOnInsert"]["idea"] == "User original"


def test_save_pipeline_step_finalized_idea(wi_mocks):
    """save_pipeline_step should write finalized_idea to $set when provided."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id=None)

    save_pipeline_step(
        run_id="run-ps2", idea="Original", pipeline_key="req",
        iteration=1, content="c", finalized_idea="Refined version",
    )

    ops = mock_collection.update_one.call_args[0][1]
    assert ops["$set"]["finalized_idea"] == "Refined version"


def test_save_pipeline_step_no_finalized_idea_omits_field(wi_mocks):
    """When finalized_idea is empty, it should NOT appear in $set."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id=None)

    save_pipeline_step(
        run_id="run-ps3", idea="X", pipeline_key="req",
        iteration=1, content="c",
    )

    ops = mock_collection.update_one.call_args[0][1]
    assert "finalized_idea" not in ops["$set"]


# ── update_section_critique ─────────────────────────────────────


def test_update_section_critique_updates_record(wi_mocks):
    """update_section_critique should $set critique on the matching iteration record."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(modified_count=1)

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


def test_update_section_critique_returns_false_when_no_match(wi_mocks):
    """update_section_critique should return False when no record matches."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(modified_count=0)

    result = update_section_critique(
        run_id="run-1",
        section_key="executive_summary",
        iteration=99,
        critique="Some critique",
    )

    assert result is False


def test_update_section_critique_returns_false_on_error(wi_mocks):
    """update_section_critique should catch PyMongo errors and return False."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("timeout")

    result = update_section_critique(
        run_id="run-1",
        section_key="executive_summary",
        iteration=1,
        critique="Some critique",
    )

    assert result is False


# ── find_unfinalized ────────────────────────────────────────────


def test_find_unfinalized_returns_runs(wi_mocks):
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

    mock_collection, mock_db = wi_mocks
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = working_docs
    mock_collection.find.return_value = mock_cursor


    runs = find_unfinalized()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run-abc"
    assert runs[0]["idea"] == "Dark mode"
    assert runs[0]["iteration"] == 3
    assert "executive_summary" in runs[0]["sections"]
    assert "problem_statement" in runs[0]["sections"]
    assert runs[0]["exec_summary_iterations"] == 0  # no top-level array
    assert runs[0]["req_breakdown_iterations"] == 0  # no top-level array


def test_find_unfinalized_empty_when_all_completed(wi_mocks):
    """find_unfinalized should return empty if every run is completed."""
    mock_collection, mock_db = wi_mocks
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = []
    mock_collection.find.return_value = mock_cursor


    runs = find_unfinalized()
    assert runs == []


def test_find_unfinalized_returns_empty_on_error(wi_mocks):
    """find_unfinalized should return [] on database errors."""
    with patch(
        "crewai_productfeature_planner.mongodb.working_ideas._common.get_db",
        side_effect=ServerSelectionTimeoutError("timeout"),
    ):
        assert find_unfinalized() == []


def test_find_unfinalized_skips_empty_draft_sections(wi_mocks):
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

    mock_collection, mock_db = wi_mocks
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = working_docs
    mock_collection.find.return_value = mock_cursor


    runs = find_unfinalized()
    assert runs[0]["sections"] == ["executive_summary"]


# ── get_run_documents ───────────────────────────────────────────


def test_get_run_documents_returns_doc(wi_mocks):
    """get_run_documents should return the single doc for a run as a list."""
    doc = {
        "run_id": "run-1",
        "idea": "Test",
        "section": {
            "executive_summary": [{"content": "...", "iteration": 1, "critique": "", "updated_date": ""}],
        },
        "status": "inprogress",
    }
    mock_collection, mock_db = wi_mocks
    mock_collection.find_one.return_value = doc


    result = get_run_documents("run-1")
    assert result == [doc]
    mock_collection.find_one.assert_called_once_with(
        {"run_id": "run-1", "status": {"$nin": ["completed", "archived"]}}
    )


def test_get_run_documents_returns_empty_on_error(wi_mocks):
    """get_run_documents should return [] on database errors."""
    mock_collection, mock_db = wi_mocks
    mock_collection.find_one.side_effect = ServerSelectionTimeoutError("timeout")


    result = get_run_documents("run-1")
    assert result == []


def test_get_run_documents_empty_result(wi_mocks):
    """get_run_documents should handle not-found result."""
    mock_collection, mock_db = wi_mocks
    mock_collection.find_one.return_value = None


    result = get_run_documents("run-nonexistent")
    assert result == []


# ── mark_completed ──────────────────────────────────────────────


def test_mark_completed_updates_document(wi_mocks):
    """mark_completed should set status=completed on the doc for the run_id."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(modified_count=1)

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


def test_mark_completed_returns_zero_on_db_error(wi_mocks):
    """mark_completed should catch PyMongo errors and return 0."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("timeout")

    count = mark_completed("run-abc")
    assert count == 0


def test_mark_completed_returns_zero_when_no_docs(wi_mocks):
    """mark_completed should return 0 when run_id has no documents."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(modified_count=0)

    count = mark_completed("run-nonexistent")
    assert count == 0


def test_find_unfinalized_excludes_completed_runs(wi_mocks):
    """find_unfinalized should exclude documents with status=completed but include failed."""
    mock_collection, mock_db = wi_mocks
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = []  # all excluded by query filter
    mock_collection.find.return_value = mock_cursor


    runs = find_unfinalized()
    assert runs == []
    # Verify the query filters out completed only (failed is resumable)
    find_call = mock_collection.find.call_args
    query = find_call[0][0]
    assert "completed" in query["status"]["$nin"]
    assert "failed" not in query["status"]["$nin"]


def test_find_unfinalized_counts_exec_summary_array(wi_mocks):
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

    mock_collection, mock_db = wi_mocks
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = working_docs
    mock_collection.find.return_value = mock_cursor


    runs = find_unfinalized()
    assert runs[0]["exec_summary_iterations"] == 4
    # effective iteration should be max(draft=0, exec=4)
    assert runs[0]["iteration"] == 4
    assert runs[0]["sections"] == []  # no draft sections
    assert runs[0]["req_breakdown_iterations"] == 0  # no requirements_breakdown array


def test_find_unfinalized_counts_req_breakdown_array(wi_mocks):
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

    mock_collection, mock_db = wi_mocks
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = working_docs
    mock_collection.find.return_value = mock_cursor


    runs = find_unfinalized()
    assert runs[0]["req_breakdown_iterations"] == 3
    assert runs[0]["exec_summary_iterations"] == 1


# ── save_executive_summary ──────────────────────────────────


def test_save_executive_summary_upserts(wi_mocks):
    """save_executive_summary should push to top-level executive_summary array."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id=None)

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


def test_save_executive_summary_with_critique(wi_mocks):
    """save_executive_summary should store critique when provided."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(upserted_id=None)

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


def test_save_executive_summary_returns_none_on_error(wi_mocks):
    """save_executive_summary should return None on PyMongo error."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("timeout")

    result = save_executive_summary(
        run_id="run-err",
        idea="Test",
        iteration=1,
        content="content",
    )
    assert result is None


# ── update_executive_summary_critique ───────────────────────


def test_update_executive_summary_critique_updates_record(wi_mocks):
    """update_executive_summary_critique should update critique on matching iteration."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(modified_count=1)

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


def test_update_executive_summary_critique_returns_false_on_error(wi_mocks):
    """update_executive_summary_critique should return False on PyMongo error."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("timeout")

    result = update_executive_summary_critique(
        run_id="run-err",
        iteration=1,
        critique="critique text",
    )
    assert result is False


# ── save_finalized_idea ─────────────────────────────────────


def test_save_finalized_idea_updates_doc(wi_mocks):
    """save_finalized_idea should $set finalized_idea on the document."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(modified_count=1)

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


def test_save_finalized_idea_returns_false_on_error(wi_mocks):
    """save_finalized_idea should catch PyMongo errors and return False."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("timeout")

    result = save_finalized_idea(
        run_id="run-err",
        finalized_idea="content",
    )
    assert result is False


# ── save_output_file ──────────────────────────────────────────


def test_save_output_file_updates_doc(wi_mocks):
    """save_output_file should $set output_file on the document."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(modified_count=1)

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


def test_save_output_file_returns_false_on_error(wi_mocks):
    """save_output_file should catch PyMongo errors and return False."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("timeout")

    result = save_output_file(run_id="run-err", output_file="some/path.md")
    assert result is False


def test_save_output_file_returns_false_when_no_match(wi_mocks):
    """save_output_file should return False when no document matches."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(modified_count=0)

    result = save_output_file(run_id="nonexistent", output_file="path.md")
    assert result is False


# ── find_completed_without_output ─────────────────────────────


def test_find_completed_without_output_returns_docs(wi_mocks):
    """Should return completed docs that have no output_file."""
    docs = [
        {"run_id": "run-1", "status": "completed", "idea": "Idea 1"},
        {"run_id": "run-2", "status": "completed", "idea": "Idea 2"},
    ]
    mock_collection, mock_db = wi_mocks
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = docs
    mock_collection.find.return_value = mock_cursor

    result = find_completed_without_output()

    assert len(result) == 2
    assert result[0]["run_id"] == "run-1"
    # Verify the query uses $or for missing/null/empty output_file
    call_args = mock_collection.find.call_args
    query = call_args[0][0]
    assert query["status"] == "completed"
    assert "$or" in query


def test_find_completed_without_output_returns_empty(wi_mocks):
    """Should return empty list when all completed docs have output_file."""
    mock_collection, mock_db = wi_mocks
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = []
    mock_collection.find.return_value = mock_cursor

    result = find_completed_without_output()
    assert result == []


# ── get_output_file ───────────────────────────────────────────


def test_get_output_file_returns_path(wi_mocks):
    """Should return the output_file value from the document."""
    mock_collection, mock_db = wi_mocks
    mock_collection.find_one.return_value = {
        "output_file": "output/prds/2026/02/prd_v1.md",
    }

    result = get_output_file("run-1")

    assert result == "output/prds/2026/02/prd_v1.md"
    mock_collection.find_one.assert_called_once_with(
        {"run_id": "run-1"},
        {"output_file": 1, "_id": 0},
    )


def test_get_output_file_returns_none_when_missing(wi_mocks):
    """Should return None when document has no output_file."""
    mock_collection, mock_db = wi_mocks
    mock_collection.find_one.return_value = {}

    assert get_output_file("run-1") is None


def test_get_output_file_returns_none_when_empty_string(wi_mocks):
    """Should return None when output_file is empty string."""
    mock_collection, mock_db = wi_mocks
    mock_collection.find_one.return_value = {"output_file": ""}

    assert get_output_file("run-1") is None


def test_get_output_file_returns_none_when_no_doc(wi_mocks):
    """Should return None when document is not found."""
    mock_collection, mock_db = wi_mocks
    mock_collection.find_one.return_value = None

    assert get_output_file("run-1") is None


def test_get_output_file_returns_none_on_error(wi_mocks):
    """Should return None on database error."""
    mock_collection, mock_db = wi_mocks
    mock_db.__getitem__ = MagicMock(
        side_effect=ServerSelectionTimeoutError("timeout"),
    )

    assert get_output_file("run-1") is None


def test_find_completed_without_output_returns_empty_on_error(wi_mocks):
    """Should return empty list on database error."""
    mock_collection, mock_db = wi_mocks
    mock_db.__getitem__ = MagicMock(
        side_effect=ServerSelectionTimeoutError("timeout"),
    )

    result = find_completed_without_output()
    assert result == []


# ── mark_paused ───────────────────────────────────────────────


def test_mark_paused_updates_status(wi_mocks):
    """mark_paused should set status=paused on the document."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(modified_count=1)

    result = mark_paused("run-1")

    assert result == 1
    call_args = mock_collection.update_one.call_args
    query = call_args[0][0]
    update = call_args[0][1]
    assert query == {"run_id": "run-1"}
    assert update["$set"]["status"] == "paused"
    assert "update_date" in update["$set"]


def test_mark_paused_returns_zero_when_no_match(wi_mocks):
    """mark_paused should return 0 when no document matches."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(modified_count=0)

    assert mark_paused("nonexistent") == 0


def test_mark_paused_returns_zero_on_error(wi_mocks):
    """mark_paused should return 0 on database error."""
    mock_collection, mock_db = wi_mocks
    mock_db.__getitem__ = MagicMock(
        side_effect=ServerSelectionTimeoutError("timeout"),
    )

    assert mark_paused("run-1") == 0


# ── mark_archived ─────────────────────────────────────────────


def test_mark_archived_updates_status(wi_mocks):
    """mark_archived should set status=archived on the doc."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(modified_count=1)

    count = mark_archived("run-archive")

    assert count == 1
    call_args = mock_collection.update_one.call_args
    assert call_args[0][0] == {"run_id": "run-archive"}
    update_set = call_args[0][1]["$set"]
    assert update_set["status"] == "archived"
    assert "archived_at" in update_set
    assert "update_date" in update_set


def test_mark_archived_returns_zero_when_no_match(wi_mocks):
    """mark_archived should return 0 when no doc matches."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(modified_count=0)

    assert mark_archived("run-missing") == 0


def test_mark_archived_returns_zero_on_error(wi_mocks):
    """mark_archived should return 0 on database error."""
    mock_collection, mock_db = wi_mocks
    mock_db.__getitem__ = MagicMock(
        side_effect=ServerSelectionTimeoutError("timeout"),
    )

    assert mark_archived("run-1") == 0


# ── find_unfinalized — archived exclusion ─────────────────────


def test_find_unfinalized_excludes_archived(wi_mocks):
    """find_unfinalized should exclude archived docs (same as completed)."""
    mock_collection, mock_db = wi_mocks
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = []
    mock_collection.find.return_value = mock_cursor

    find_unfinalized()

    # Verify the query excludes both "completed" and "archived"
    call_args = mock_collection.find.call_args
    query = call_args[0][0]
    assert "archived" in query["status"]["$nin"]
    assert "completed" in query["status"]["$nin"]


# ── ensure_section_field ──────────────────────────────────────


def test_ensure_section_field_creates_missing(wi_mocks):
    """ensure_section_field should create section={} when field is missing."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(modified_count=1)

    result = ensure_section_field("run-1")

    assert result is True
    call_args = mock_collection.update_one.call_args
    assert call_args[0][0] == {"run_id": "run-1", "section": {"$exists": False}}
    assert call_args[0][1] == {"$set": {"section": {}}}


def test_ensure_section_field_noop_when_exists(wi_mocks):
    """ensure_section_field should return False when section already exists."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(modified_count=0)

    result = ensure_section_field("run-1")

    assert result is False


def test_ensure_section_field_returns_false_on_error(wi_mocks):
    """ensure_section_field should return False on database error."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("timeout")

    result = ensure_section_field("run-1")

    assert result is False


# ── find_unfinalized — section_missing flag ───────────────────


def test_find_unfinalized_flags_section_missing(wi_mocks):
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

    mock_collection, mock_db = wi_mocks
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = working_docs
    mock_collection.find.return_value = mock_cursor

    runs = find_unfinalized()
    assert len(runs) == 1
    assert runs[0]["section_missing"] is True


def test_find_unfinalized_section_not_missing_when_present(wi_mocks):
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

    mock_collection, mock_db = wi_mocks
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = working_docs
    mock_collection.find.return_value = mock_cursor

    runs = find_unfinalized()
    assert len(runs) == 1
    assert runs[0]["section_missing"] is False


# ── find_completed_without_confluence ────────────────────────────────


class TestFindCompletedWithoutConfluence:

    def test_returns_docs_not_published(self, wi_mocks):
        """Returns completed docs whose run_id has no published delivery record."""
        mock_collection, mock_db = wi_mocks
        completed_id_docs = [
            {"_id": "id1", "run_id": "r1"},
            {"_id": "id2", "run_id": "r2"},
        ]
        full_docs = [
            {"run_id": "r1", "status": "completed", "idea": "idea1"},
            {"run_id": "r2", "status": "completed", "idea": "idea2"},
        ]

        # Phase 1: projection query returns id docs
        # Phase 3: full doc fetch returns full docs
        proj_cursor = MagicMock()
        proj_cursor.sort.return_value = completed_id_docs
        full_cursor = MagicMock()
        full_cursor.sort.return_value = full_docs
        mock_collection.find.side_effect = [proj_cursor, full_cursor]

        # productRequirements collection — no published records
        mock_pr_col = MagicMock()
        mock_pr_col.find.return_value = []
        mock_db.__getitem__ = lambda self, name: (
            mock_pr_col if name == "productRequirements" else mock_collection
        )

        result = find_completed_without_confluence()

        assert len(result) == 2
        assert result[0]["run_id"] == "r1"

    def test_excludes_published_runs(self, wi_mocks):
        """Runs with confluence_published=True in productRequirements are excluded."""
        mock_collection, mock_db = wi_mocks
        completed_id_docs = [
            {"_id": "id1", "run_id": "r1"},
            {"_id": "id2", "run_id": "r2"},
        ]
        full_docs = [
            {"run_id": "r2", "status": "completed", "idea": "idea2"},
        ]

        # Phase 1: projection, Phase 3: full docs (only r2)
        proj_cursor = MagicMock()
        proj_cursor.sort.return_value = completed_id_docs
        full_cursor = MagicMock()
        full_cursor.sort.return_value = full_docs
        mock_collection.find.side_effect = [proj_cursor, full_cursor]

        # productRequirements: r1 is already published
        mock_pr_col = MagicMock()
        mock_pr_col.find.return_value = [{"run_id": "r1"}]
        mock_db.__getitem__ = lambda self, name: (
            mock_pr_col if name == "productRequirements" else mock_collection
        )

        result = find_completed_without_confluence()

        assert len(result) == 1
        assert result[0]["run_id"] == "r2"

    def test_returns_empty_on_no_results(self, wi_mocks):
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = []
        mock_collection, mock_db = wi_mocks
        mock_collection.find.return_value = mock_cursor

        result = find_completed_without_confluence()
        assert result == []

    def test_returns_empty_on_db_error(self, wi_mocks):
        from pymongo.errors import PyMongoError
        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas._common.get_db",
            side_effect=PyMongoError("connection failed"),
        ):
            result = find_completed_without_confluence()
            assert result == []


# ── save_project_ref ──────────────────────────────────────────────


def test_save_project_ref(wi_mocks):
    """save_project_ref should $set project_id on the working idea doc."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(
        modified_count=1, upserted_id=None, matched_count=1,
    )

    count = save_project_ref("run-1", "proj-abc")

    assert count == 1
    mock_db.__getitem__.assert_called_with(WORKING_COLLECTION)
    call_args = mock_collection.update_one.call_args
    assert call_args[0][0] == {"run_id": "run-1"}
    set_fields = call_args[0][1]["$set"]
    assert set_fields["project_id"] == "proj-abc"
    assert "update_date" in set_fields
    # Without idea= the idea field should NOT be set
    assert "idea" not in set_fields
    # Verify upsert is enabled
    assert call_args[1].get("upsert") is True
    # $setOnInsert should include run_id and status
    insert_fields = call_args[0][1]["$setOnInsert"]
    assert insert_fields["run_id"] == "run-1"
    assert insert_fields["status"] == "inprogress"
    assert "idea" not in insert_fields


def test_save_project_ref_with_idea(wi_mocks):
    """save_project_ref should persist idea only in $set (not $setOnInsert)."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(
        modified_count=1, upserted_id=None, matched_count=1,
    )

    count = save_project_ref("run-1", "proj-abc", idea="Build a dashboard")

    assert count == 1
    call_args = mock_collection.update_one.call_args
    set_fields = call_args[0][1]["$set"]
    assert set_fields["idea"] == "Build a dashboard"
    insert_fields = call_args[0][1]["$setOnInsert"]
    assert "idea" not in insert_fields


def test_save_project_ref_upserts_new_doc(wi_mocks):
    """save_project_ref should create a stub document when none exists."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(
        modified_count=0, upserted_id="new-obj-id", matched_count=0,
    )

    count = save_project_ref("run-new", "proj-xyz")

    # Should count the upsert as a modification
    assert count == 1
    call_args = mock_collection.update_one.call_args
    assert call_args[1].get("upsert") is True


def test_save_project_ref_db_error(wi_mocks):
    """save_project_ref should return 0 on DB failure."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("fail")

    assert save_project_ref("run-1", "proj-abc") == 0


# ── save_slack_context ────────────────────────────────────────────


def test_save_slack_context(wi_mocks):
    """save_slack_context should $set channel/thread and use upsert."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(
        modified_count=1, upserted_id=None, matched_count=1,
    )

    count = save_slack_context("run-1", "C123", "ts-1")

    assert count == 1
    call_args = mock_collection.update_one.call_args
    assert call_args[0][0] == {"run_id": "run-1"}
    set_fields = call_args[0][1]["$set"]
    assert set_fields["slack_channel"] == "C123"
    assert set_fields["slack_thread_ts"] == "ts-1"
    assert "update_date" in set_fields
    # Without idea= the idea field should NOT be set
    assert "idea" not in set_fields
    # Verify upsert is enabled
    assert call_args[1].get("upsert") is True
    # $setOnInsert should include run_id and status
    insert_fields = call_args[0][1]["$setOnInsert"]
    assert insert_fields["run_id"] == "run-1"
    assert insert_fields["status"] == "inprogress"
    assert "idea" not in insert_fields


def test_save_slack_context_with_idea(wi_mocks):
    """save_slack_context should persist idea only in $set (not $setOnInsert)."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(
        modified_count=1, upserted_id=None, matched_count=1,
    )

    count = save_slack_context("run-1", "C123", "ts-1", idea="Build a dashboard")

    assert count == 1
    call_args = mock_collection.update_one.call_args
    set_fields = call_args[0][1]["$set"]
    assert set_fields["idea"] == "Build a dashboard"
    insert_fields = call_args[0][1]["$setOnInsert"]
    assert "idea" not in insert_fields


def test_save_slack_context_upserts_new_doc(wi_mocks):
    """save_slack_context should create a stub document when none exists."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.return_value = MagicMock(
        modified_count=0, upserted_id="new-obj-id", matched_count=0,
    )

    count = save_slack_context("run-new", "C456", "ts-2")

    # Should count the upsert as a modification
    assert count == 1


def test_save_slack_context_db_error(wi_mocks):
    """save_slack_context should return 0 on DB failure."""
    mock_collection, mock_db = wi_mocks
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("fail")

    assert save_slack_context("run-1", "C123", "ts-1") == 0


# ── find_ideas_by_project ────────────────────────────────────────


class TestFindIdeasByProject:

    def test_returns_ideas_for_project(self, wi_mocks):
        docs = [
            {
                "run_id": "r1", "idea": "idea1", "status": "inprogress",
                "project_id": "proj-1", "created_at": "2026-03-01T00:00:00Z",
                "section": {"problem_statement": [{"content": "x", "iteration": 1}]},
                "executive_summary": [{"content": "y"}],
            },
            {
                "run_id": "r2", "idea": "idea2", "status": "paused",
                "project_id": "proj-1", "created_at": "2026-02-28T00:00:00Z",
                "section": {}, "executive_summary": [],
            },
        ]
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = docs
        mock_collection, mock_db = wi_mocks
        mock_collection.find.return_value = mock_cursor

        result = find_ideas_by_project("proj-1")

        assert len(result) == 2
        assert result[0]["run_id"] == "r1"
        assert result[0]["status"] == "inprogress"
        # problem_statement (1) + executive_summary top-level (1) = 2
        assert result[0]["sections_done"] == 2
        assert result[1]["run_id"] == "r2"
        assert result[1]["status"] == "paused"
        assert result[1]["sections_done"] == 0
        # Verify query uses $or with project_id and excludes archived+completed
        query = mock_collection.find.call_args[0][0]
        assert query["status"] == {"$nin": ["archived", "completed"]}
        assert "$or" in query
        assert {"project_id": "proj-1"} in query["$or"]

    def test_returns_empty_when_no_ideas(self, wi_mocks):
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = []
        mock_collection, mock_db = wi_mocks
        mock_collection.find.return_value = mock_cursor

        result = find_ideas_by_project("proj-empty")
        assert result == []

    def test_returns_empty_on_db_error(self, wi_mocks):
        from pymongo.errors import PyMongoError
        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas._common.get_db",
            side_effect=PyMongoError("connection failed"),
        ):
            result = find_ideas_by_project("proj-1")
            assert result == []

    def test_backfills_orphaned_idea_via_channel(self, wi_mocks):
        """When channel is provided, orphaned ideas whose crew job
        matches the channel should be backfilled and returned."""
        mock_collection, mock_db = wi_mocks

        # First .find() returns no ideas for project_id query
        proj_cursor = MagicMock()
        proj_cursor.sort.return_value = []

        # Second .find() returns an orphan (no project_id)
        orphan_doc = {
            "run_id": "orphan-1",
            "idea": "Orphan idea",
            "status": "failed",
            "created_at": "2026-03-01T00:00:00Z",
            "section": {},
            "executive_summary": [],
        }

        mock_collection.find.side_effect = [proj_cursor, [orphan_doc]]

        # Mock find_job to return a job in the same channel
        with patch(
            "crewai_productfeature_planner.mongodb.crew_jobs.repository.find_job",
            return_value={"slack_channel": "C123"},
        ):
            result = find_ideas_by_project("proj-1", channel="C123")

        assert len(result) == 1
        assert result[0]["run_id"] == "orphan-1"
        assert result[0]["status"] == "failed"
        # Verify backfill update_one was called
        update_calls = mock_collection.update_one.call_args_list
        assert any(
            call[0][0] == {"run_id": "orphan-1"}
            and call[0][1]["$set"]["project_id"] == "proj-1"
            for call in update_calls
        )

    def test_no_backfill_when_channel_not_provided(self, wi_mocks):
        """Without channel, no backfill should occur and $or has only project_id."""
        mock_collection, mock_db = wi_mocks

        proj_cursor = MagicMock()
        proj_cursor.sort.return_value = []
        mock_collection.find.return_value = proj_cursor

        result = find_ideas_by_project("proj-1")

        assert result == []
        # .find() called only once (main query, no orphan backfill)
        assert mock_collection.find.call_count == 1
        # The query $or should only contain the project_id condition
        query = mock_collection.find.call_args[0][0]
        assert len(query["$or"]) == 1

    def test_backfill_skips_wrong_channel(self, wi_mocks):
        """Orphaned ideas whose crew job is in a different channel
        should NOT be included."""
        mock_collection, mock_db = wi_mocks

        proj_cursor = MagicMock()
        proj_cursor.sort.return_value = []

        orphan_doc = {
            "run_id": "orphan-2",
            "idea": "Wrong channel idea",
            "status": "inprogress",
            "created_at": "2026-03-01T00:00:00Z",
            "section": {},
            "executive_summary": [],
        }
        mock_collection.find.side_effect = [proj_cursor, [orphan_doc]]

        with patch(
            "crewai_productfeature_planner.mongodb.crew_jobs.repository.find_job",
            return_value={"slack_channel": "C-OTHER"},
        ):
            result = find_ideas_by_project("proj-1", channel="C123")

        assert result == []

    def test_backfill_skips_orphan_without_crew_job(self, wi_mocks):
        """Orphaned ideas with no matching crew job should be ignored."""
        mock_collection, mock_db = wi_mocks

        proj_cursor = MagicMock()
        proj_cursor.sort.return_value = []

        orphan_doc = {
            "run_id": "orphan-3",
            "idea": "No job idea",
            "status": "failed",
            "created_at": "2026-03-01T00:00:00Z",
            "section": {},
            "executive_summary": [],
        }
        mock_collection.find.side_effect = [proj_cursor, [orphan_doc]]

        with patch(
            "crewai_productfeature_planner.mongodb.crew_jobs.repository.find_job",
            return_value=None,
        ):
            result = find_ideas_by_project("proj-1", channel="C123")

        assert result == []

    def test_backfill_does_not_duplicate_existing(self, wi_mocks):
        """If an idea already has project_id and an orphan with the same
        run_id exists (impossible but defensive), no duplicate is added."""
        mock_collection, mock_db = wi_mocks

        existing_doc = {
            "run_id": "r1",
            "idea": "Existing",
            "status": "inprogress",
            "project_id": "proj-1",
            "created_at": "2026-03-01T00:00:00Z",
            "section": {},
            "executive_summary": [],
        }
        proj_cursor = MagicMock()
        proj_cursor.sort.return_value = [existing_doc]

        # Orphan with same run_id (edge case)
        orphan_doc = {
            "run_id": "r1",
            "idea": "Existing",
            "status": "inprogress",
            "created_at": "2026-03-01T00:00:00Z",
            "section": {},
            "executive_summary": [],
        }
        mock_collection.find.side_effect = [proj_cursor, [orphan_doc]]

        with patch(
            "crewai_productfeature_planner.mongodb.crew_jobs.repository.find_job",
            return_value={"slack_channel": "C123"},
        ):
            result = find_ideas_by_project("proj-1", channel="C123")

        # Should only get 1 result, not 2
        assert len(result) == 1
        assert result[0]["run_id"] == "r1"

    def test_backfill_db_error_returns_gracefully(self, wi_mocks):
        """If the backfill DB query fails, the main query result
        should still be returned."""
        from pymongo.errors import PyMongoError

        mock_collection, mock_db = wi_mocks

        existing_doc = {
            "run_id": "r1",
            "idea": "Existing",
            "status": "completed",
            "project_id": "proj-1",
            "created_at": "2026-03-01T00:00:00Z",
            "section": {},
            "executive_summary": [],
        }
        proj_cursor = MagicMock()
        proj_cursor.sort.return_value = [existing_doc]

        # Second .find() (orphan query) raises
        mock_collection.find.side_effect = [proj_cursor, PyMongoError("fail")]

        result = find_ideas_by_project("proj-1", channel="C123")

        # Should still return the existing idea
        assert len(result) == 1
        assert result[0]["run_id"] == "r1"

    # -- Regression tests: inprogress ideas must always appear ----------

    def test_inprogress_without_project_id_found_via_channel(self, wi_mocks):
        """An inprogress idea that lacks project_id but has a matching
        slack_channel must appear in the list when channel is given.

        Regression test — this scenario caused invisible ideas in v0.7.0.
        """
        mock_collection, mock_db = wi_mocks

        # The main $or query now returns this orphan directly
        # because it matches slack_channel + no project_id.
        orphan_doc = {
            "run_id": "orphan-inprogress",
            "idea": "Running idea without project",
            "status": "inprogress",
            "slack_channel": "C123",
            "created_at": "2026-03-02T00:00:00Z",
            "section": {},
            "executive_summary": [],
        }
        proj_cursor = MagicMock()
        proj_cursor.sort.return_value = [orphan_doc]

        # Backfill orphan query returns empty (already found in main)
        mock_collection.find.side_effect = [proj_cursor, []]

        result = find_ideas_by_project("proj-1", channel="C123")

        assert len(result) == 1
        assert result[0]["run_id"] == "orphan-inprogress"
        assert result[0]["status"] == "inprogress"

        # Verify the main query includes the channel-based $or condition
        query = mock_collection.find.call_args_list[0][0][0]
        assert "$or" in query
        assert len(query["$or"]) == 2  # project_id + channel orphan

    def test_channel_condition_in_or_query(self, wi_mocks):
        """When channel is provided, the $or query must include a
        condition for orphan ideas matching that channel."""
        mock_collection, mock_db = wi_mocks

        proj_cursor = MagicMock()
        proj_cursor.sort.return_value = []
        mock_collection.find.side_effect = [proj_cursor, []]

        find_ideas_by_project("proj-1", channel="C999")

        query = mock_collection.find.call_args_list[0][0][0]
        or_conds = query["$or"]
        # Should have project_id condition + channel orphan condition
        assert {"project_id": "proj-1"} in or_conds
        # Second condition should match slack_channel + no project_id
        channel_cond = [c for c in or_conds if c.get("slack_channel") == "C999"]
        assert len(channel_cond) == 1
        assert "$or" in channel_cond[0]  # nested $or for null/missing project_id

    def test_inline_backfill_sets_project_id_on_orphan(self, wi_mocks):
        """Orphaned ideas found via channel match should get their
        project_id backfilled inline."""
        mock_collection, mock_db = wi_mocks

        orphan_doc = {
            "run_id": "orphan-needs-backfill",
            "idea": "Orphan needing backfill",
            "status": "inprogress",
            "slack_channel": "C123",
            "created_at": "2026-03-02T00:00:00Z",
            "section": {},
            "executive_summary": [],
            # No project_id field at all
        }
        proj_cursor = MagicMock()
        proj_cursor.sort.return_value = [orphan_doc]
        mock_collection.find.side_effect = [proj_cursor, []]

        result = find_ideas_by_project("proj-1", channel="C123")

        assert len(result) == 1
        # Verify update_one was called to backfill project_id
        update_calls = mock_collection.update_one.call_args_list
        backfill_calls = [
            c for c in update_calls
            if c[0][0] == {"run_id": "orphan-needs-backfill"}
        ]
        assert len(backfill_calls) >= 1
        assert backfill_calls[0][0][1]["$set"]["project_id"] == "proj-1"

    def test_inprogress_with_project_id_always_listed(self, wi_mocks):
        """An inprogress idea WITH the correct project_id must always
        be returned regardless of channel."""
        mock_collection, mock_db = wi_mocks

        doc = {
            "run_id": "running-idea",
            "idea": "Currently running idea",
            "status": "inprogress",
            "project_id": "proj-1",
            "created_at": "2026-03-02T12:00:00Z",
            "section": {"executive_summary": [{"content": "x", "iteration": 1}]},
            "executive_summary": [{"content": "y"}],
        }
        proj_cursor = MagicMock()
        proj_cursor.sort.return_value = [doc]
        mock_collection.find.return_value = proj_cursor

        # No channel — the project_id match alone should work
        result = find_ideas_by_project("proj-1")

        assert len(result) == 1
        assert result[0]["run_id"] == "running-idea"
        assert result[0]["status"] == "inprogress"

    def test_all_non_archived_statuses_listed(self, wi_mocks):
        """All statuses except 'archived' must appear in results:
        inprogress, paused, completed, failed."""
        mock_collection, mock_db = wi_mocks

        docs = [
            {"run_id": "r-ip", "idea": "I1", "status": "inprogress",
             "project_id": "proj-1", "created_at": "2026-03-04T04:00:00Z",
             "section": {}, "executive_summary": []},
            {"run_id": "r-pa", "idea": "I2", "status": "paused",
             "project_id": "proj-1", "created_at": "2026-03-04T03:00:00Z",
             "section": {}, "executive_summary": []},
            {"run_id": "r-co", "idea": "I3", "status": "completed",
             "project_id": "proj-1", "created_at": "2026-03-04T02:00:00Z",
             "section": {}, "executive_summary": []},
            {"run_id": "r-fa", "idea": "I4", "status": "failed",
             "project_id": "proj-1", "created_at": "2026-03-04T01:00:00Z",
             "section": {}, "executive_summary": []},
        ]
        proj_cursor = MagicMock()
        proj_cursor.sort.return_value = docs
        mock_collection.find.return_value = proj_cursor

        result = find_ideas_by_project("proj-1")

        assert len(result) == 4
        statuses = {r["status"] for r in result}
        assert statuses == {"inprogress", "paused", "completed", "failed"}

    def test_backfill_uses_doc_slack_channel_first(self, wi_mocks):
        """_backfill_orphaned_ideas should match on the document's own
        slack_channel before falling back to crew_jobs lookup."""
        mock_collection, mock_db = wi_mocks

        # Main query returns nothing
        proj_cursor = MagicMock()
        proj_cursor.sort.return_value = []

        # Orphan has slack_channel set directly
        orphan_doc = {
            "run_id": "orphan-sc",
            "idea": "Orphan with slack_channel",
            "status": "inprogress",
            "slack_channel": "C123",
            "created_at": "2026-03-02T00:00:00Z",
            "section": {},
            "executive_summary": [],
        }
        mock_collection.find.side_effect = [proj_cursor, [orphan_doc]]

        # find_job should NOT need to be called because the document's
        # own slack_channel matches.
        with patch(
            "crewai_productfeature_planner.mongodb.crew_jobs.repository.find_job",
        ) as mock_find_job:
            result = find_ideas_by_project("proj-1", channel="C123")

        assert len(result) == 1
        assert result[0]["run_id"] == "orphan-sc"
        # find_job was never called — matched on document's slack_channel
        mock_find_job.assert_not_called()


# ── _doc_to_idea_dict ────────────────────────────────────────────


class TestDocToIdeaDict:
    """Tests for _doc_to_idea_dict helper used by find_ideas_by_project."""

    def _call(self, doc):
        from crewai_productfeature_planner.mongodb.working_ideas._queries import (
            _doc_to_idea_dict,
        )
        return _doc_to_idea_dict(doc)

    def test_counts_executive_summary_as_section(self):
        """Top-level executive_summary should count toward sections_done."""
        doc = {
            "run_id": "r1",
            "idea": "test",
            "status": "inprogress",
            "section": {
                "problem_statement": [{"content": "x", "iteration": 1}],
            },
            "executive_summary": [{"content": "y"}],
        }
        result = self._call(doc)
        # 1 section key + 1 executive_summary = 2
        assert result["sections_done"] == 2

    def test_no_double_count_executive_summary(self):
        """If executive_summary appears in both section obj and top-level,
        it should only be counted once."""
        doc = {
            "run_id": "r1",
            "idea": "test",
            "status": "inprogress",
            "section": {
                "executive_summary": [{"content": "x", "iteration": 1}],
                "problem_statement": [{"content": "y", "iteration": 1}],
            },
            "executive_summary": [{"content": "z"}],
        }
        result = self._call(doc)
        # executive_summary already counted in section obj, not double-counted
        assert result["sections_done"] == 2

    def test_completed_forces_full_sections(self):
        """A completed idea should show sections_done == total_sections."""
        doc = {
            "run_id": "r1",
            "idea": "done idea",
            "status": "completed",
            "section": {},
            "executive_summary": [],
        }
        result = self._call(doc)
        assert result["sections_done"] == result["total_sections"]
        assert result["sections_done"] == 12

    def test_nine_sections_plus_exec_gives_ten(self):
        """Nine section keys + executive_summary = 10/12."""
        section_keys = [
            "problem_statement", "user_personas",
            "functional_requirements", "no_functional_requirements",
            "edge_cases", "error_handling", "success_metrics",
            "dependencies", "assumptions",
        ]
        doc = {
            "run_id": "r1",
            "idea": "full draft",
            "status": "inprogress",
            "section": {k: [{"content": "x", "iteration": 1}] for k in section_keys},
            "executive_summary": [{"content": "y"}],
        }
        result = self._call(doc)
        assert result["sections_done"] == 10
        assert result["total_sections"] == 12

    def test_no_exec_summary_gives_nine(self):
        """Nine section keys but no executive_summary = 9/12."""
        section_keys = [
            "problem_statement", "user_personas",
            "functional_requirements", "no_functional_requirements",
            "edge_cases", "error_handling", "success_metrics",
            "dependencies", "assumptions",
        ]
        doc = {
            "run_id": "r1",
            "idea": "missing exec",
            "status": "inprogress",
            "section": {k: [{"content": "x", "iteration": 1}] for k in section_keys},
            "executive_summary": [],
        }
        result = self._call(doc)
        assert result["sections_done"] == 9


# ── _doc_to_product_dict ─────────────────────────────────────


class TestDocToProductDict:
    """Tests for _doc_to_product_dict — smart jira_completed logic."""

    _BASE_DOC = {
        "run_id": "r1",
        "idea": "test idea",
        "status": "completed",
        "section": {},
        "executive_summary": [],
    }

    def _call(self, doc, delivery):
        from crewai_productfeature_planner.mongodb.working_ideas._queries import (
            _doc_to_product_dict,
        )
        return _doc_to_product_dict(doc, delivery)

    def test_bogus_jira_completed_treated_as_false(self):
        """When jira_completed=True but no tickets and phase != subtasks_done,
        the product dict should report jira_completed=False."""
        delivery = {
            "jira_completed": True,
            "jira_tickets": [],
        }
        result = self._call(self._BASE_DOC, delivery)
        assert result["jira_completed"] is False

    def test_subtasks_done_honours_jira_completed(self):
        """When jira_phase='subtasks_done' and jira_completed=True,
        jira_completed should be True even without ticket records."""
        doc = {**self._BASE_DOC, "jira_phase": "subtasks_done"}
        delivery = {
            "jira_completed": True,
            "jira_tickets": [],
        }
        result = self._call(doc, delivery)
        assert result["jira_completed"] is True

    def test_real_tickets_honours_jira_completed(self):
        """When jira_completed=True and tickets exist,
        jira_completed should be True."""
        delivery = {
            "jira_completed": True,
            "jira_tickets": [{"key": "PROJ-1"}],
        }
        result = self._call(self._BASE_DOC, delivery)
        assert result["jira_completed"] is True

    def test_jira_not_completed_stays_false(self):
        """When jira_completed=False, jira_completed should be False."""
        delivery = {
            "jira_completed": False,
            "jira_tickets": [],
        }
        result = self._call(self._BASE_DOC, delivery)
        assert result["jira_completed"] is False

    def test_no_delivery_record(self):
        """When there is no delivery record at all, jira_completed=False."""
        result = self._call(self._BASE_DOC, None)
        assert result["jira_completed"] is False
        assert result["jira_tickets"] == []

    def test_active_jira_phase_overrides_delivery_with_tickets(self):
        """When jira_phase is an active phase (not subtasks_done), the
        delivery record is overridden even if it has tickets."""
        doc = {**self._BASE_DOC, "jira_phase": "skeleton_pending"}
        delivery = {
            "jira_completed": True,
            "jira_tickets": [{"key": f"PROJ-{i}"} for i in range(45)],
        }
        result = self._call(doc, delivery)
        assert result["jira_completed"] is False

    def test_epics_stories_done_phase_not_completed(self):
        """jira_phase='epics_stories_done' means work remains."""
        doc = {**self._BASE_DOC, "jira_phase": "epics_stories_done"}
        delivery = {"jira_completed": True, "jira_tickets": [{"key": "P-1"}]}
        result = self._call(doc, delivery)
        assert result["jira_completed"] is False

    def test_skeleton_approved_phase_not_completed(self):
        """jira_phase='skeleton_approved' means work remains."""
        doc = {**self._BASE_DOC, "jira_phase": "skeleton_approved"}
        delivery = {"jira_completed": True, "jira_tickets": []}
        result = self._call(doc, delivery)
        assert result["jira_completed"] is False

    def test_subtasks_done_always_completed(self):
        """jira_phase='subtasks_done' with jira_completed=True in delivery
        means done — even without ticket records (e.g. review skip)."""
        doc = {**self._BASE_DOC, "jira_phase": "subtasks_done"}
        delivery = {"jira_completed": True, "jira_tickets": []}
        result = self._call(doc, delivery)
        assert result["jira_completed"] is True

    def test_subtasks_done_stale_without_evidence(self):
        """Regression: jira_phase='subtasks_done' but delivery has no
        tickets and jira_completed=False → stale data, should be False.

        This prevents the :white_check_mark: Jira Ticketing resurfacing
        when a one-time data fix cleaned the delivery record but missed
        the workingIdeas jira_phase field.
        """
        doc = {**self._BASE_DOC, "jira_phase": "subtasks_done"}
        delivery = {"jira_completed": False, "jira_tickets": []}
        result = self._call(doc, delivery)
        assert result["jira_completed"] is False

    def test_subtasks_done_no_delivery_record(self):
        """Regression: jira_phase='subtasks_done' with no delivery record
        at all is stale — should be False."""
        doc = {**self._BASE_DOC, "jira_phase": "subtasks_done"}
        result = self._call(doc, None)
        assert result["jira_completed"] is False

    def test_subtasks_done_with_tickets_but_not_marked(self):
        """jira_phase='subtasks_done' with tickets in delivery → True,
        even if jira_completed not explicitly set."""
        doc = {**self._BASE_DOC, "jira_phase": "subtasks_done"}
        delivery = {"jira_completed": False, "jira_tickets": [{"key": "P-1"}]}
        result = self._call(doc, delivery)
        assert result["jira_completed"] is True

    def test_stale_confluence_url_does_not_imply_published(self):
        """Regression: A stale confluence_url on the workingIdeas doc
        must NOT cause confluence_published=True when the delivery
        record says it's not published.

        This was the root cause of incorrect checkmarks after a
        one-time script reset the delivery record but missed
        the workingIdeas confluence_url field.
        """
        doc = {
            **self._BASE_DOC,
            "confluence_url": "https://wiki.example.com/stale-page",
        }
        delivery = {
            "confluence_published": False,
            "confluence_url": "",
            "jira_completed": False,
            "jira_tickets": [],
        }
        result = self._call(doc, delivery)
        assert result["confluence_published"] is False
        # The URL should still be available for display purposes
        assert result["confluence_url"] == "https://wiki.example.com/stale-page"

    def test_confluence_url_only_in_delivery_record(self):
        """When confluence_url is only in the delivery record, it should be used."""
        doc = {**self._BASE_DOC}
        delivery = {
            "confluence_published": True,
            "confluence_url": "https://wiki.example.com/published",
            "jira_completed": False,
            "jira_tickets": [],
        }
        result = self._call(doc, delivery)
        assert result["confluence_published"] is True
        assert result["confluence_url"] == "https://wiki.example.com/published"

    def test_no_delivery_record_no_url_not_published(self):
        """No delivery record and no URL → not published."""
        result = self._call(self._BASE_DOC, None)
        assert result["confluence_published"] is False
        assert result["confluence_url"] == ""

    def test_stale_confluence_url_no_delivery_record(self):
        """Stale URL on doc but no delivery record → not published."""
        doc = {
            **self._BASE_DOC,
            "confluence_url": "https://wiki.example.com/stale",
        }
        result = self._call(doc, None)
        assert result["confluence_published"] is False
        assert result["confluence_url"] == "https://wiki.example.com/stale"


# ── fail_unfinalized_on_startup ───────────────────────────────


class TestFailUnfinalizedOnStartup:
    """Tests for fail_unfinalized_on_startup."""

    def test_marks_paused_ideas_as_failed(self, wi_mocks):
        """Paused working ideas should be marked as failed on startup."""
        mock_collection, mock_db = wi_mocks
        mock_collection.find.return_value = [
            {
                "_id": "id1",
                "run_id": "run-1",
                "idea": "Test idea",
                "status": "paused",
                "slack_channel": "C123",
                "slack_thread_ts": "1234.5678",
            },
        ]
        mock_collection.update_one.return_value = MagicMock(modified_count=1)

        result = fail_unfinalized_on_startup()

        assert len(result) == 1
        assert result[0]["run_id"] == "run-1"
        assert result[0]["prev_status"] == "paused"
        assert result[0]["slack_channel"] == "C123"
        assert result[0]["slack_thread_ts"] == "1234.5678"
        # Verify update call
        update_call = mock_collection.update_one.call_args
        set_fields = update_call[0][1]["$set"]
        assert set_fields["status"] == "failed"
        assert "server restarted" in set_fields["error"].lower()

    def test_marks_inprogress_ideas_as_failed(self, wi_mocks):
        """In-progress working ideas should be marked as failed on startup."""
        mock_collection, mock_db = wi_mocks
        mock_collection.find.return_value = [
            {
                "_id": "id2",
                "run_id": "run-2",
                "idea": "Another idea",
                "status": "inprogress",
            },
        ]
        mock_collection.update_one.return_value = MagicMock(modified_count=1)

        result = fail_unfinalized_on_startup()

        assert len(result) == 1
        assert result[0]["run_id"] == "run-2"
        assert result[0]["prev_status"] == "inprogress"

    def test_skips_completed_archived_failed(self, wi_mocks):
        """Completed, archived, and failed ideas should not be modified."""
        mock_collection, mock_db = wi_mocks
        mock_collection.find.return_value = []

        result = fail_unfinalized_on_startup()

        assert result == []
        # Verify the query excludes completed, archived, and failed
        query = mock_collection.find.call_args[0][0]
        assert query["status"]["$nin"] == ["completed", "archived", "failed"]

    def test_returns_empty_when_no_unfinalized(self, wi_mocks):
        """Should return empty list when all ideas are finalized."""
        mock_collection, mock_db = wi_mocks
        mock_collection.find.return_value = []

        result = fail_unfinalized_on_startup()
        assert result == []
        mock_collection.update_one.assert_not_called()

    def test_handles_multiple_ideas(self, wi_mocks):
        """Should mark multiple unfinalized ideas as failed."""
        mock_collection, mock_db = wi_mocks
        mock_collection.find.return_value = [
            {"_id": "id1", "run_id": "r1", "idea": "Idea 1", "status": "paused"},
            {"_id": "id2", "run_id": "r2", "idea": "Idea 2", "status": "inprogress"},
        ]
        mock_collection.update_one.return_value = MagicMock(modified_count=1)

        result = fail_unfinalized_on_startup()

        assert len(result) == 2
        assert mock_collection.update_one.call_count == 2

    def test_returns_empty_on_db_error(self, wi_mocks):
        """Should return empty list on database errors."""
        from pymongo.errors import PyMongoError
        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas._common.get_db",
            side_effect=PyMongoError("connection failed"),
        ):
            result = fail_unfinalized_on_startup()
            assert result == []


# ── save_jira_phase ───────────────────────────────────────────


class TestSaveJiraPhase:
    """Tests for save_jira_phase."""

    def test_persists_phase_to_document(self, wi_mocks):
        """Should update the jira_phase field on the working idea doc."""
        mock_collection, mock_db = wi_mocks
        mock_collection.update_one.return_value = MagicMock(modified_count=1)

        result = save_jira_phase("run-abc", "skeleton_pending")

        assert result == 1
        call_args = mock_collection.update_one.call_args
        assert call_args[0][0] == {"run_id": "run-abc"}
        set_fields = call_args[0][1]["$set"]
        assert set_fields["jira_phase"] == "skeleton_pending"
        assert "update_date" in set_fields

    def test_clears_phase_with_empty_string(self, wi_mocks):
        """Should allow clearing the phase (rejection case)."""
        mock_collection, mock_db = wi_mocks
        mock_collection.update_one.return_value = MagicMock(modified_count=1)

        result = save_jira_phase("run-abc", "")

        assert result == 1
        set_fields = mock_collection.update_one.call_args[0][1]["$set"]
        assert set_fields["jira_phase"] == ""

    def test_returns_zero_when_no_match(self, wi_mocks):
        """Should return 0 when no document matches the run_id."""
        mock_collection, mock_db = wi_mocks
        mock_collection.update_one.return_value = MagicMock(modified_count=0)

        result = save_jira_phase("nonexistent", "skeleton_pending")
        assert result == 0

    def test_returns_zero_on_db_error(self, wi_mocks):
        """Should catch PyMongoError and return 0."""
        from pymongo.errors import PyMongoError

        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas._common.get_db",
            side_effect=PyMongoError("connection failed"),
        ):
            result = save_jira_phase("run-abc", "skeleton_pending")
            assert result == 0


# ── save_jira_skeleton / get_jira_skeleton ────────────────────


class TestSaveJiraSkeleton:
    """Tests for save_jira_skeleton and get_jira_skeleton."""

    def test_saves_skeleton_text(self, wi_mocks):
        """Should persist skeleton text on the working-idea document."""
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            save_jira_skeleton,
        )

        mock_collection, mock_db = wi_mocks
        mock_collection.update_one.return_value = MagicMock(modified_count=1)

        result = save_jira_skeleton("run-abc", "## Epic 1\n- Story A")

        assert result == 1
        call_args = mock_collection.update_one.call_args
        assert call_args[0][0] == {"run_id": "run-abc"}
        set_fields = call_args[0][1]["$set"]
        assert set_fields["jira_skeleton"] == "## Epic 1\n- Story A"
        assert "update_date" in set_fields

    def test_returns_zero_on_no_match(self, wi_mocks):
        """Should return 0 when no document matches."""
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            save_jira_skeleton,
        )

        mock_collection, mock_db = wi_mocks
        mock_collection.update_one.return_value = MagicMock(modified_count=0)

        result = save_jira_skeleton("nonexistent", "skeleton")
        assert result == 0

    def test_returns_zero_on_db_error(self, wi_mocks):
        """Should catch PyMongoError and return 0."""
        from pymongo.errors import PyMongoError
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            save_jira_skeleton,
        )

        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas._common.get_db",
            side_effect=PyMongoError("connection failed"),
        ):
            result = save_jira_skeleton("run-abc", "skeleton")
            assert result == 0

    def test_get_skeleton_returns_text(self, wi_mocks):
        """Should return the stored skeleton text."""
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            get_jira_skeleton,
        )

        mock_collection, mock_db = wi_mocks
        mock_collection.find_one.return_value = {
            "jira_skeleton": "## Epic 1\n- Story A",
        }

        result = get_jira_skeleton("run-abc")
        assert result == "## Epic 1\n- Story A"
        mock_collection.find_one.assert_called_once_with(
            {"run_id": "run-abc"},
            {"jira_skeleton": 1},
        )

    def test_get_skeleton_returns_empty_when_missing(self, wi_mocks):
        """Should return empty string when field is absent."""
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            get_jira_skeleton,
        )

        mock_collection, mock_db = wi_mocks
        mock_collection.find_one.return_value = {}

        result = get_jira_skeleton("run-abc")
        assert result == ""

    def test_get_skeleton_returns_empty_on_no_doc(self, wi_mocks):
        """Should return empty string when document doesn't exist."""
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            get_jira_skeleton,
        )

        mock_collection, mock_db = wi_mocks
        mock_collection.find_one.return_value = None

        result = get_jira_skeleton("run-abc")
        assert result == ""

    def test_get_skeleton_returns_empty_on_db_error(self, wi_mocks):
        """Should catch PyMongoError and return empty string."""
        from pymongo.errors import PyMongoError
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            get_jira_skeleton,
        )

        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas._common.get_db",
            side_effect=PyMongoError("connection failed"),
        ):
            result = get_jira_skeleton("run-abc")
            assert result == ""


# ── save/get_jira_epics_stories_output ────────────────────────


class TestSaveJiraEpicsStoriesOutput:
    """Tests for save_jira_epics_stories_output and get_jira_epics_stories_output."""

    def test_saves_output_text(self, wi_mocks):
        """Should persist epics/stories output on the working-idea document."""
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            save_jira_epics_stories_output,
        )

        mock_collection, mock_db = wi_mocks
        mock_collection.update_one.return_value = MagicMock(modified_count=1)

        result = save_jira_epics_stories_output("run-abc", "Epic: PRD-1\nStories: PRD-2")

        assert result == 1
        call_args = mock_collection.update_one.call_args
        assert call_args[0][0] == {"run_id": "run-abc"}
        set_fields = call_args[0][1]["$set"]
        assert set_fields["jira_epics_stories_output"] == "Epic: PRD-1\nStories: PRD-2"
        assert "update_date" in set_fields

    def test_returns_zero_on_no_match(self, wi_mocks):
        """Should return 0 when no document matches."""
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            save_jira_epics_stories_output,
        )

        mock_collection, mock_db = wi_mocks
        mock_collection.update_one.return_value = MagicMock(modified_count=0)

        result = save_jira_epics_stories_output("nonexistent", "output")
        assert result == 0

    def test_returns_zero_on_db_error(self, wi_mocks):
        """Should catch PyMongoError and return 0."""
        from pymongo.errors import PyMongoError
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            save_jira_epics_stories_output,
        )

        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas._common.get_db",
            side_effect=PyMongoError("connection failed"),
        ):
            result = save_jira_epics_stories_output("run-abc", "output")
            assert result == 0

    def test_get_output_returns_text(self, wi_mocks):
        """Should return the stored epics/stories output text."""
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            get_jira_epics_stories_output,
        )

        mock_collection, mock_db = wi_mocks
        mock_collection.find_one.return_value = {
            "jira_epics_stories_output": "Epic: PRD-1\nStories: PRD-2",
        }

        result = get_jira_epics_stories_output("run-abc")
        assert result == "Epic: PRD-1\nStories: PRD-2"
        mock_collection.find_one.assert_called_once_with(
            {"run_id": "run-abc"},
            {"jira_epics_stories_output": 1},
        )

    def test_get_output_returns_empty_when_missing(self, wi_mocks):
        """Should return empty string when field is absent."""
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            get_jira_epics_stories_output,
        )

        mock_collection, mock_db = wi_mocks
        mock_collection.find_one.return_value = {}

        result = get_jira_epics_stories_output("run-abc")
        assert result == ""

    def test_get_output_returns_empty_on_no_doc(self, wi_mocks):
        """Should return empty string when document doesn't exist."""
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            get_jira_epics_stories_output,
        )

        mock_collection, mock_db = wi_mocks
        mock_collection.find_one.return_value = None

        result = get_jira_epics_stories_output("run-abc")
        assert result == ""

    def test_get_output_returns_empty_on_db_error(self, wi_mocks):
        """Should catch PyMongoError and return empty string."""
        from pymongo.errors import PyMongoError
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            get_jira_epics_stories_output,
        )

        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas._common.get_db",
            side_effect=PyMongoError("connection failed"),
        ):
            result = get_jira_epics_stories_output("run-abc")
            assert result == ""


# ── find_completed_ideas_by_project ───────────────────────────


class TestFindCompletedIdeasByProject:
    """Tests for the find_completed_ideas_by_project query."""

    def test_returns_enriched_products(self, wi_mocks):
        """Should return enriched product dicts for completed ideas."""
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            find_completed_ideas_by_project,
        )

        mock_collection, mock_db = wi_mocks
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = [
            {
                "run_id": "run-x",
                "idea": "Test idea",
                "status": "completed",
                "created_at": "2026-03-05T00:00:00Z",
                "executive_summary": [{"iteration": 1, "content": "exec"}],
                "section": {},
                "confluence_url": "https://wiki/page",
                "jira_phase": "skeleton_approved",
            },
        ]
        mock_collection.find.return_value = mock_cursor

        with patch(
            "crewai_productfeature_planner.mongodb.product_requirements.get_delivery_record",
            return_value={
                "confluence_published": True,
                "jira_completed": False,
                "jira_tickets": ["PROJ-1"],
            },
        ):
            result = find_completed_ideas_by_project("proj-1")

        assert len(result) == 1
        product = result[0]
        assert product["run_id"] == "run-x"
        assert product["confluence_published"] is True
        assert product["jira_completed"] is False
        assert product["jira_phase"] == "skeleton_approved"
        assert product["jira_tickets"] == ["PROJ-1"]

    def test_returns_empty_on_no_results(self, wi_mocks):
        """Should return empty list when no completed ideas exist."""
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            find_completed_ideas_by_project,
        )

        mock_collection, mock_db = wi_mocks
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = []
        mock_collection.find.return_value = mock_cursor

        result = find_completed_ideas_by_project("proj-empty")
        assert result == []

    def test_skips_docs_without_run_id(self, wi_mocks):
        """Documents without run_id should be skipped."""
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            find_completed_ideas_by_project,
        )

        mock_collection, mock_db = wi_mocks
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = [
            {"status": "completed", "idea": "No run_id"},
        ]
        mock_collection.find.return_value = mock_cursor

        result = find_completed_ideas_by_project("proj-1")
        assert result == []

    def test_query_uses_completed_status(self, wi_mocks):
        """The MongoDB query should filter for status='completed'."""
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            find_completed_ideas_by_project,
        )

        mock_collection, mock_db = wi_mocks
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = []
        mock_collection.find.return_value = mock_cursor

        find_completed_ideas_by_project("proj-1")

        query = mock_collection.find.call_args[0][0]
        assert query["status"] == "completed"

    def test_returns_empty_on_db_error(self):
        """Should return empty list on PyMongoError."""
        from pymongo.errors import PyMongoError

        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            find_completed_ideas_by_project,
        )

        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas._common.get_db",
            side_effect=PyMongoError("connection failed"),
        ):
            result = find_completed_ideas_by_project("proj-1")
            assert result == []

    def test_delivery_record_none_uses_defaults(self, wi_mocks):
        """When no delivery record exists, defaults should be used."""
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            find_completed_ideas_by_project,
        )

        mock_collection, mock_db = wi_mocks
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = [
            {
                "run_id": "run-y",
                "idea": "New idea",
                "status": "completed",
                "executive_summary": [],
                "section": {},
            },
        ]
        mock_collection.find.return_value = mock_cursor

        with patch(
            "crewai_productfeature_planner.mongodb.product_requirements.get_delivery_record",
            return_value=None,
        ):
            result = find_completed_ideas_by_project("proj-1")

        assert len(result) == 1
        product = result[0]
        assert product["confluence_published"] is False
        assert product["jira_completed"] is False
        assert product["jira_tickets"] == []
