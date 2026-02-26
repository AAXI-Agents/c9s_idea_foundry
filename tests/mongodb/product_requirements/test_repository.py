"""Tests for mongodb.product_requirements.repository — delivery tracking."""

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.mongodb.product_requirements.repository import (
    PRODUCT_REQUIREMENTS_COLLECTION,
    _compute_status,
    append_jira_ticket,
    find_pending_delivery,
    get_delivery_record,
    get_jira_tickets,
    upsert_delivery_record,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── _compute_status ──────────────────────────────────────────


class TestComputeStatus:
    """Tests for the status computation helper."""

    def test_both_false_is_pending(self):
        assert _compute_status(False, False) == "pending"

    def test_confluence_only_is_partial(self):
        assert _compute_status(True, False) == "partial"

    def test_jira_only_is_partial(self):
        assert _compute_status(False, True) == "partial"

    def test_both_true_is_completed(self):
        assert _compute_status(True, True) == "completed"


# ── PRODUCT_REQUIREMENTS_COLLECTION constant ─────────────────


def test_collection_name():
    assert PRODUCT_REQUIREMENTS_COLLECTION == "productRequirements"


# ── get_delivery_record ──────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_get_delivery_record_found(mock_get_db):
    """Should return the document when it exists."""
    mock_col = MagicMock()
    mock_col.find_one.return_value = {"run_id": "r1", "status": "pending"}
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_get_db.return_value = mock_db

    result = get_delivery_record("r1")

    assert result == {"run_id": "r1", "status": "pending"}
    mock_col.find_one.assert_called_once_with({"run_id": "r1"})


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_get_delivery_record_not_found(mock_get_db):
    """Should return None when document does not exist."""
    mock_col = MagicMock()
    mock_col.find_one.return_value = None
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_get_db.return_value = mock_db

    result = get_delivery_record("nonexistent")

    assert result is None


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_get_delivery_record_handles_error(mock_get_db):
    """Should return None on PyMongo errors."""
    from pymongo.errors import ServerSelectionTimeoutError

    mock_get_db.side_effect = ServerSelectionTimeoutError("timeout")

    result = get_delivery_record("r1")

    assert result is None


# ── find_pending_delivery ────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_find_pending_delivery_returns_docs(mock_get_db):
    """Should return pending and partial delivery records."""
    docs = [
        {"run_id": "r1", "status": "pending"},
        {"run_id": "r2", "status": "partial"},
    ]
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = docs
    mock_col = MagicMock()
    mock_col.find.return_value = mock_cursor
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_get_db.return_value = mock_db

    result = find_pending_delivery()

    assert len(result) == 2
    mock_col.find.assert_called_once_with(
        {"status": {"$in": ["pending", "partial"]}}
    )


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_find_pending_delivery_empty(mock_get_db):
    """Should return empty list when nothing pending."""
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = []
    mock_col = MagicMock()
    mock_col.find.return_value = mock_cursor
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_get_db.return_value = mock_db

    result = find_pending_delivery()

    assert result == []


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_find_pending_delivery_handles_error(mock_get_db):
    """Should return empty list on error."""
    from pymongo.errors import ServerSelectionTimeoutError

    mock_get_db.side_effect = ServerSelectionTimeoutError("timeout")

    result = find_pending_delivery()

    assert result == []


# ── upsert_delivery_record ───────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_upsert_creates_new_record(mock_get_db):
    """Should create a new record when none exists."""
    mock_col = MagicMock()
    mock_col.find_one.return_value = None  # no existing record
    mock_col.update_one.return_value = MagicMock(
        upserted_id="abc", modified_count=0,
    )
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_get_db.return_value = mock_db

    result = upsert_delivery_record(
        "r1",
        confluence_published=True,
        confluence_url="https://wiki.test.com/page/1",
        jira_completed=False,
    )

    assert result is True
    call_args = mock_col.update_one.call_args
    assert call_args[0][0] == {"run_id": "r1"}
    set_fields = call_args[0][1]["$set"]
    assert set_fields["confluence_published"] is True
    assert set_fields["confluence_url"] == "https://wiki.test.com/page/1"
    assert set_fields["jira_completed"] is False
    assert set_fields["status"] == "partial"  # confluence=True, jira=False
    assert call_args[1]["upsert"] is True


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_upsert_updates_existing_record(mock_get_db):
    """Should update an existing partial record to completed."""
    mock_col = MagicMock()
    mock_col.find_one.return_value = {
        "run_id": "r1",
        "confluence_published": True,
        "jira_completed": False,
        "status": "partial",
    }
    mock_col.update_one.return_value = MagicMock(
        upserted_id=None, modified_count=1,
    )
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_get_db.return_value = mock_db

    result = upsert_delivery_record(
        "r1",
        jira_completed=True,
        jira_output="PROJ-1, PROJ-2",
    )

    assert result is True
    set_fields = mock_col.update_one.call_args[0][1]["$set"]
    assert set_fields["jira_completed"] is True
    assert set_fields["jira_output"] == "PROJ-1, PROJ-2"
    assert set_fields["status"] == "completed"  # both now True


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_upsert_only_updates_provided_fields(mock_get_db):
    """Fields not passed (None) should not appear in $set."""
    mock_col = MagicMock()
    mock_col.find_one.return_value = None
    mock_col.update_one.return_value = MagicMock(
        upserted_id="new", modified_count=0,
    )
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_get_db.return_value = mock_db

    upsert_delivery_record("r1", confluence_published=True)

    set_fields = mock_col.update_one.call_args[0][1]["$set"]
    assert "confluence_published" in set_fields
    assert "jira_completed" not in set_fields
    assert "jira_output" not in set_fields
    assert "confluence_url" not in set_fields


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_upsert_records_error(mock_get_db):
    """Should store error message when passed."""
    mock_col = MagicMock()
    mock_col.find_one.return_value = {"run_id": "r1", "status": "pending"}
    mock_col.update_one.return_value = MagicMock(
        upserted_id=None, modified_count=1,
    )
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_get_db.return_value = mock_db

    upsert_delivery_record("r1", error="Pipeline timeout")

    set_fields = mock_col.update_one.call_args[0][1]["$set"]
    assert set_fields["error"] == "Pipeline timeout"


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_upsert_handles_db_error(mock_get_db):
    """Should return False on PyMongo errors."""
    from pymongo.errors import ServerSelectionTimeoutError

    mock_get_db.side_effect = ServerSelectionTimeoutError("timeout")

    result = upsert_delivery_record("r1", confluence_published=True)

    assert result is False


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_upsert_preserves_existing_flags_on_partial_update(mock_get_db):
    """When only updating jira, confluence_published should be preserved."""
    mock_col = MagicMock()
    mock_col.find_one.return_value = {
        "run_id": "r1",
        "confluence_published": True,
        "jira_completed": False,
    }
    mock_col.update_one.return_value = MagicMock(
        upserted_id=None, modified_count=1,
    )
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_get_db.return_value = mock_db

    upsert_delivery_record("r1", jira_completed=True)

    set_fields = mock_col.update_one.call_args[0][1]["$set"]
    # status should be "completed" because both are now True
    assert set_fields["status"] == "completed"


# ── upsert_delivery_record with jira_tickets ─────────────────


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_upsert_with_jira_tickets(mock_get_db):
    """Should include jira_tickets in $set when provided."""
    mock_col = MagicMock()
    mock_col.find_one.return_value = None
    mock_col.update_one.return_value = MagicMock(
        upserted_id="new", modified_count=0,
    )
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_get_db.return_value = mock_db

    tickets = [{"key": "PRD-1", "type": "Epic"}]
    upsert_delivery_record("r1", jira_tickets=tickets)

    set_fields = mock_col.update_one.call_args[0][1]["$set"]
    assert set_fields["jira_tickets"] == tickets


# ── append_jira_ticket ───────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_append_jira_ticket_pushes(mock_get_db):
    """Should $push a new ticket to the jira_tickets array."""
    mock_col = MagicMock()
    # No duplicate
    mock_col.find_one.return_value = None
    mock_col.update_one.return_value = MagicMock(
        upserted_id=None, modified_count=1,
    )
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_get_db.return_value = mock_db

    result = append_jira_ticket("r1", {"key": "PRD-10", "type": "Epic"})

    assert result is True
    update_args = mock_col.update_one.call_args[0][1]
    assert update_args["$push"]["jira_tickets"]["key"] == "PRD-10"


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_append_jira_ticket_skips_duplicate(mock_get_db):
    """Should skip if ticket key already exists in the array."""
    mock_col = MagicMock()
    # Existing ticket found
    mock_col.find_one.return_value = {"run_id": "r1", "jira_tickets": [{"key": "PRD-10"}]}
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_get_db.return_value = mock_db

    result = append_jira_ticket("r1", {"key": "PRD-10", "type": "Epic"})

    assert result is True
    mock_col.update_one.assert_not_called()


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_append_jira_ticket_handles_error(mock_get_db):
    """Should return False on DB error."""
    from pymongo.errors import ServerSelectionTimeoutError

    mock_get_db.side_effect = ServerSelectionTimeoutError("timeout")

    result = append_jira_ticket("r1", {"key": "PRD-10", "type": "Epic"})

    assert result is False


# ── get_jira_tickets ─────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_get_jira_tickets_returns_list(mock_get_db):
    """Should return the jira_tickets list from the delivery record."""
    mock_col = MagicMock()
    mock_col.find_one.return_value = {
        "run_id": "r1",
        "jira_tickets": [{"key": "PRD-1", "type": "Epic"}],
    }
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_get_db.return_value = mock_db

    result = get_jira_tickets("r1")

    assert result == [{"key": "PRD-1", "type": "Epic"}]


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_get_jira_tickets_returns_empty_when_absent(mock_get_db):
    """Should return [] when no jira_tickets field or no record."""
    mock_col = MagicMock()
    mock_col.find_one.return_value = {"run_id": "r1"}
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_get_db.return_value = mock_db

    result = get_jira_tickets("r1")

    assert result == []


@patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
def test_get_jira_tickets_returns_empty_for_nonexistent(mock_get_db):
    """Should return [] when no record exists."""
    mock_col = MagicMock()
    mock_col.find_one.return_value = None
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_get_db.return_value = mock_db

    result = get_jira_tickets("nonexistent")

    assert result == []
