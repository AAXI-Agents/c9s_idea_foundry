"""Tests for mongodb.finalized_ideas.repository — save_finalized."""

from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from crewai_productfeature_planner.mongodb.finalized_ideas.repository import (
    FINALIZED_COLLECTION,
    save_finalized,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── save_finalized ────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.finalized_ideas.repository.get_db")
def test_save_finalized_inserts_doc(mock_get_db):
    """save_finalized should insert into finalizeIdeas."""
    mock_collection = MagicMock()
    mock_collection.insert_one.return_value = MagicMock(inserted_id="fin456")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = save_finalized(
        run_id="run-1",
        idea="SSO",
        iteration=3,
        final_prd="# Final PRD",
        confluence_xhtml="<h1>Final PRD</h1>",
    )

    mock_db.__getitem__.assert_called_with(FINALIZED_COLLECTION)
    mock_collection.insert_one.assert_called_once()
    doc = mock_collection.insert_one.call_args[0][0]
    assert doc["run_id"] == "run-1"
    assert doc["final_prd"] == "# Final PRD"
    assert doc["confluence_xhtml"] == "<h1>Final PRD</h1>"
    assert doc["total_iterations"] == 3
    assert result == "fin456"


@patch("crewai_productfeature_planner.mongodb.finalized_ideas.repository.get_db")
def test_save_finalized_without_xhtml(mock_get_db):
    """save_finalized without confluence_xhtml should default to empty string."""
    mock_collection = MagicMock()
    mock_collection.insert_one.return_value = MagicMock(inserted_id="fin789")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    save_finalized(run_id="run-2", idea="Auth", iteration=1, final_prd="# PRD")

    doc = mock_collection.insert_one.call_args[0][0]
    assert doc["confluence_xhtml"] == ""


@patch("crewai_productfeature_planner.mongodb.finalized_ideas.repository.get_db")
def test_save_finalized_returns_none_on_db_error(mock_get_db):
    """save_finalized should catch PyMongo errors and return None."""
    mock_collection = MagicMock()
    mock_collection.insert_one.side_effect = ServerSelectionTimeoutError(
        "connection refused"
    )
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = save_finalized(
        run_id="r1", idea="X", iteration=1, final_prd="# PRD"
    )
    assert result is None
