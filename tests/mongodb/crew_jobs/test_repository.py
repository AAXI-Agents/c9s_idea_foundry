"""Tests for mongodb.crew_jobs.repository — job lifecycle tracking."""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from crewai_productfeature_planner.mongodb.crew_jobs.repository import (
    CREW_JOBS_COLLECTION,
    _human_duration,
    _ms_between,
    create_job,
    fail_incomplete_jobs_on_startup,
    find_active_job,
    find_job,
    list_jobs,
    reactivate_job,
    update_job_completed,
    update_job_failed,
    update_job_started,
    update_job_status,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── helper tests ──────────────────────────────────────────────


class TestHumanDuration:
    """Tests for the _human_duration helper."""

    def test_zero(self):
        assert _human_duration(0) == "0h 0m 0s"

    def test_seconds_only(self):
        assert _human_duration(5_000) == "0h 0m 5s"

    def test_minutes_and_seconds(self):
        assert _human_duration(90_000) == "0h 1m 30s"

    def test_hours_minutes_seconds(self):
        assert _human_duration(3_723_000) == "1h 2m 3s"

    def test_exact_hour(self):
        assert _human_duration(3_600_000) == "1h 0m 0s"

    def test_large_value(self):
        # 10 hours, 5 minutes, 30 seconds = 36330 seconds = 36330000 ms
        assert _human_duration(36_330_000) == "10h 5m 30s"


class TestMsBetween:
    """Tests for the _ms_between helper."""

    def test_zero_difference(self):
        t = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert _ms_between(t, t) == 0

    def test_positive_difference(self):
        start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc)
        assert _ms_between(start, end) == 5_000

    def test_fractional_seconds(self):
        start = datetime(2026, 1, 1, 0, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 0, 1, 500_000, tzinfo=timezone.utc)
        assert _ms_between(start, end) == 1_500


# ── find_active_job ─────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_find_active_job_returns_doc(mock_get_db):
    """find_active_job should return an incomplete job if one exists."""
    active = {"job_id": "run-1", "status": "running"}
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = active
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = find_active_job()
    assert result == active
    mock_collection.find_one.assert_called_once_with(
        {"status": {"$in": ["queued", "running", "awaiting_approval"]}}
    )


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_find_active_job_returns_none_when_empty(mock_get_db):
    """find_active_job should return None when no active jobs."""
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = None
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    assert find_active_job() is None


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_find_active_job_returns_none_on_error(mock_get_db):
    """find_active_job should return None on database errors."""
    mock_collection = MagicMock()
    mock_collection.find_one.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    assert find_active_job() is None


# ── create_job ────────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_create_job_inserts_doc(mock_get_db):
    """create_job should insert a queued job document."""
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = None      # no active job
    mock_collection.insert_one.return_value = MagicMock(inserted_id="job123")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = create_job(job_id="run-1", flow_name="prd", idea="Dark mode")

    mock_db.__getitem__.assert_called_with(CREW_JOBS_COLLECTION)
    mock_collection.insert_one.assert_called_once()
    doc = mock_collection.insert_one.call_args[0][0]
    assert doc["job_id"] == "run-1"
    assert doc["flow_name"] == "prd"
    assert doc["idea"] == "Dark mode"
    assert doc["status"] == "queued"
    assert doc["error"] is None
    assert doc["started_at"] is None
    assert doc["completed_at"] is None
    assert doc["queue_time_ms"] is None
    assert doc["queue_time_human"] is None
    assert doc["running_time_ms"] is None
    assert doc["running_time_human"] is None
    assert doc["queued_at"] is not None
    assert doc["updated_at"] is not None
    assert result == "job123"


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_create_job_returns_none_on_error(mock_get_db):
    """create_job should return None on database errors."""
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = None      # no active job
    mock_collection.insert_one.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = create_job(job_id="r1", flow_name="prd")
    assert result is None


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_create_job_rejects_when_active_job_exists(mock_get_db):
    """create_job should reject and return None when an active job exists."""
    active = {"job_id": "existing", "status": "running"}
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = active
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = create_job(job_id="new-job", flow_name="prd", idea="Another")
    assert result is None
    mock_collection.insert_one.assert_not_called()


# ── reactivate_job ───────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_reactivate_job_resets_fields(mock_get_db):
    """reactivate_job should reset a job to queued status."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(modified_count=1, matched_count=1)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = reactivate_job("run-1")
    assert result is True
    set_fields = mock_collection.update_one.call_args[0][1]["$set"]
    assert set_fields["status"] == "queued"
    assert set_fields["error"] is None
    assert set_fields["started_at"] is None
    assert set_fields["completed_at"] is None
    assert set_fields["queue_time_ms"] is None
    assert set_fields["running_time_ms"] is None
    assert set_fields["queued_at"] is not None
    assert set_fields["updated_at"] is not None


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_reactivate_job_returns_false_when_not_found(mock_get_db):
    """reactivate_job should return False when job doesn't exist."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(modified_count=0, matched_count=0)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = reactivate_job("nonexistent")
    assert result is False


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_reactivate_job_returns_false_on_error(mock_get_db):
    """reactivate_job should return False on database errors."""
    mock_collection = MagicMock()
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = reactivate_job("r1")
    assert result is False


# ── update_job_status ─────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_update_job_status_updates_doc(mock_get_db):
    """update_job_status should update the status field."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = update_job_status("run-1", "running")

    assert result is True
    mock_collection.update_one.assert_called_once()
    call_args = mock_collection.update_one.call_args
    assert call_args[0][0] == {"job_id": "run-1"}
    set_fields = call_args[0][1]["$set"]
    assert set_fields["status"] == "running"
    assert "updated_at" in set_fields


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_update_job_status_returns_false_on_error(mock_get_db):
    """update_job_status should return False on database errors."""
    mock_collection = MagicMock()
    mock_collection.update_one.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = update_job_status("r1", "running")
    assert result is False


# ── update_job_started ────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_update_job_started_computes_queue_time(mock_get_db):
    """update_job_started should compute queue_time from queued_at."""
    queued_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = {
        "job_id": "run-1",
        "queued_at": queued_at,
    }
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = update_job_started("run-1")

    assert result is True
    call_args = mock_collection.update_one.call_args
    set_fields = call_args[0][1]["$set"]
    assert set_fields["status"] == "running"
    assert set_fields["started_at"] is not None
    assert set_fields["queue_time_ms"] is not None
    assert isinstance(set_fields["queue_time_ms"], int)
    assert set_fields["queue_time_ms"] >= 0
    assert set_fields["queue_time_human"] is not None
    assert "h" in set_fields["queue_time_human"]


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_update_job_started_returns_false_when_not_found(mock_get_db):
    """update_job_started should return False when job not found."""
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = None
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = update_job_started("nonexistent")
    assert result is False


# ── update_job_completed ──────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_update_job_completed_computes_running_time(mock_get_db):
    """update_job_completed should compute running_time from started_at."""
    started_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = {
        "job_id": "run-1",
        "started_at": started_at,
    }
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = update_job_completed("run-1", status="completed")

    assert result is True
    call_args = mock_collection.update_one.call_args
    set_fields = call_args[0][1]["$set"]
    assert set_fields["status"] == "completed"
    assert set_fields["completed_at"] is not None
    assert set_fields["running_time_ms"] is not None
    assert isinstance(set_fields["running_time_ms"], int)
    assert set_fields["running_time_ms"] >= 0
    assert set_fields["running_time_human"] is not None


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_update_job_completed_paused(mock_get_db):
    """update_job_completed with status='paused' should set paused status."""
    started_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = {
        "job_id": "run-1",
        "started_at": started_at,
    }
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = update_job_completed("run-1", status="paused")
    assert result is True
    set_fields = mock_collection.update_one.call_args[0][1]["$set"]
    assert set_fields["status"] == "paused"


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_update_job_completed_returns_false_when_not_found(mock_get_db):
    """update_job_completed should return False when job not found."""
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = None
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = update_job_completed("nonexistent")
    assert result is False


# ── update_job_failed ─────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_update_job_failed_sets_error_and_running_time(mock_get_db):
    """update_job_failed should set error and compute running_time."""
    started_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = {
        "job_id": "run-1",
        "started_at": started_at,
        "queued_at": datetime(2025, 12, 31, 23, 59, 50, tzinfo=timezone.utc),
        "queue_time_ms": 10_000,
    }
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = update_job_failed("run-1", error="LLM timeout")

    assert result is True
    set_fields = mock_collection.update_one.call_args[0][1]["$set"]
    assert set_fields["status"] == "failed"
    assert set_fields["error"] == "LLM timeout"
    assert set_fields["completed_at"] is not None
    assert set_fields["running_time_ms"] is not None
    assert set_fields["running_time_human"] is not None


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_update_job_failed_computes_queue_time_when_never_started(mock_get_db):
    """update_job_failed should compute queue_time if job never started."""
    queued_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = {
        "job_id": "run-1",
        "started_at": None,
        "queued_at": queued_at,
        "queue_time_ms": None,
    }
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = update_job_failed("run-1", error="Server shutdown")

    assert result is True
    set_fields = mock_collection.update_one.call_args[0][1]["$set"]
    assert set_fields["status"] == "failed"
    assert "queue_time_ms" in set_fields
    assert set_fields["queue_time_ms"] is not None
    assert set_fields["queue_time_human"] is not None


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_update_job_failed_returns_false_on_error(mock_get_db):
    """update_job_failed should return False on database errors."""
    mock_collection = MagicMock()
    mock_collection.find_one.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = update_job_failed("r1", error="boom")
    assert result is False


# ── find_job ──────────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_find_job_returns_doc(mock_get_db):
    """find_job should return the matching document."""
    expected = {"job_id": "run-1", "flow_name": "prd", "status": "completed"}
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = expected
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = find_job("run-1")
    assert result == expected
    mock_collection.find_one.assert_called_once_with({"job_id": "run-1"})


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_find_job_returns_none_when_not_found(mock_get_db):
    """find_job should return None when no matching document exists."""
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = None
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    assert find_job("nonexistent") is None


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_find_job_returns_none_on_error(mock_get_db):
    """find_job should return None on database errors."""
    mock_collection = MagicMock()
    mock_collection.find_one.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    assert find_job("r1") is None


# ── list_jobs ─────────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_list_jobs_returns_all(mock_get_db):
    """list_jobs without filters should return all jobs."""
    docs = [
        {"job_id": "run-1", "status": "completed"},
        {"job_id": "run-2", "status": "failed"},
    ]
    mock_cursor = MagicMock()
    mock_sort = MagicMock()
    mock_sort.limit.return_value = docs
    mock_cursor.sort.return_value = mock_sort

    mock_collection = MagicMock()
    mock_collection.find.return_value = mock_cursor
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    result = list_jobs()
    assert result == docs
    mock_collection.find.assert_called_once_with({})


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_list_jobs_with_filters(mock_get_db):
    """list_jobs should pass status and flow_name filters."""
    mock_cursor = MagicMock()
    mock_sort = MagicMock()
    mock_sort.limit.return_value = []
    mock_cursor.sort.return_value = mock_sort

    mock_collection = MagicMock()
    mock_collection.find.return_value = mock_cursor
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    list_jobs(status="running", flow_name="prd")
    mock_collection.find.assert_called_once_with(
        {"status": "running", "flow_name": "prd"}
    )


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_list_jobs_returns_empty_on_error(mock_get_db):
    """list_jobs should return [] on database errors."""
    mock_collection = MagicMock()
    mock_collection.find.side_effect = ServerSelectionTimeoutError("timeout")
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    assert list_jobs() == []


# ── fail_incomplete_jobs_on_startup ───────────────────────────


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_fail_incomplete_marks_queued_jobs(mock_get_db):
    """fail_incomplete_jobs_on_startup should mark queued jobs as failed."""
    queued_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    incomplete_docs = [
        {
            "_id": "doc1",
            "job_id": "run-1",
            "status": "queued",
            "queued_at": queued_at,
            "started_at": None,
            "queue_time_ms": None,
        },
    ]

    mock_collection = MagicMock()
    mock_collection.find.return_value = incomplete_docs
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    recovered = fail_incomplete_jobs_on_startup()
    assert len(recovered) == 1
    assert recovered[0] == {"job_id": "run-1", "prev_status": "queued"}
    mock_collection.update_one.assert_called_once()
    set_fields = mock_collection.update_one.call_args[0][1]["$set"]
    assert set_fields["status"] == "failed"
    assert "force exit or server downtime" in set_fields["error"]
    assert set_fields["completed_at"] is not None
    assert set_fields["queue_time_ms"] is not None
    assert set_fields["queue_time_human"] is not None


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_fail_incomplete_marks_running_jobs(mock_get_db):
    """fail_incomplete_jobs_on_startup should mark running jobs as failed with running_time."""
    started_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    incomplete_docs = [
        {
            "_id": "doc2",
            "job_id": "run-2",
            "status": "running",
            "queued_at": datetime(2025, 12, 31, 23, 59, 50, tzinfo=timezone.utc),
            "started_at": started_at,
            "queue_time_ms": 10_000,
        },
    ]

    mock_collection = MagicMock()
    mock_collection.find.return_value = incomplete_docs
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    recovered = fail_incomplete_jobs_on_startup()
    assert len(recovered) == 1
    assert recovered[0] == {"job_id": "run-2", "prev_status": "running"}
    set_fields = mock_collection.update_one.call_args[0][1]["$set"]
    assert set_fields["status"] == "failed"
    assert "running" in set_fields["error"]
    assert set_fields["running_time_ms"] is not None
    assert set_fields["running_time_human"] is not None
    # queue_time should not be overwritten since it was already set
    assert "queue_time_ms" not in set_fields


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_fail_incomplete_marks_awaiting_approval_jobs(mock_get_db):
    """fail_incomplete_jobs_on_startup should handle awaiting_approval status."""
    incomplete_docs = [
        {
            "_id": "doc3",
            "job_id": "run-3",
            "status": "awaiting_approval",
            "queued_at": datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            "started_at": datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc),
            "queue_time_ms": 5_000,
        },
    ]

    mock_collection = MagicMock()
    mock_collection.find.return_value = incomplete_docs
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    recovered = fail_incomplete_jobs_on_startup()
    assert len(recovered) == 1
    assert recovered[0] == {"job_id": "run-3", "prev_status": "awaiting_approval"}
    set_fields = mock_collection.update_one.call_args[0][1]["$set"]
    assert set_fields["status"] == "failed"
    assert "awaiting_approval" in set_fields["error"]


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_fail_incomplete_no_incomplete_jobs(mock_get_db):
    """fail_incomplete_jobs_on_startup should return [] when no incomplete jobs."""
    mock_collection = MagicMock()
    mock_collection.find.return_value = []
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    recovered = fail_incomplete_jobs_on_startup()
    assert recovered == []


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_fail_incomplete_multiple_jobs(mock_get_db):
    """fail_incomplete_jobs_on_startup should handle multiple incomplete jobs."""
    incomplete_docs = [
        {
            "_id": "doc1",
            "job_id": "run-1",
            "status": "queued",
            "queued_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "started_at": None,
            "queue_time_ms": None,
        },
        {
            "_id": "doc2",
            "job_id": "run-2",
            "status": "running",
            "queued_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "started_at": datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc),
            "queue_time_ms": 5_000,
        },
        {
            "_id": "doc3",
            "job_id": "run-3",
            "status": "awaiting_approval",
            "queued_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "started_at": datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc),
            "queue_time_ms": 10_000,
        },
    ]

    mock_collection = MagicMock()
    mock_collection.find.return_value = incomplete_docs
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_get_db.return_value = mock_db

    recovered = fail_incomplete_jobs_on_startup()
    assert len(recovered) == 3
    assert {r["job_id"] for r in recovered} == {"run-1", "run-2", "run-3"}
    assert mock_collection.update_one.call_count == 3


@patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
def test_fail_incomplete_returns_zero_on_error(mock_get_db):
    """fail_incomplete_jobs_on_startup should return [] on database errors."""
    mock_get_db.side_effect = ServerSelectionTimeoutError("timeout")
    recovered = fail_incomplete_jobs_on_startup()
    assert recovered == []
