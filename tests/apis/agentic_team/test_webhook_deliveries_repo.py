"""Tests for webhook_deliveries repository (CRUD + idempotency)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import DuplicateKeyError, PyMongoError


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_db():
    """Mock get_db for all tests in this module."""
    mock_collection = MagicMock()
    mock_database = MagicMock()
    mock_database.__getitem__ = MagicMock(return_value=mock_collection)

    with patch(
        "crewai_productfeature_planner.mongodb.webhook_deliveries.repository.get_db",
        return_value=mock_database,
    ):
        yield mock_collection


# ── record_delivery ───────────────────────────────────────────


class TestRecordDelivery:
    """Test record_delivery function."""

    def test_inserts_document(self, mock_db):
        from crewai_productfeature_planner.mongodb.webhook_deliveries.repository import (
            record_delivery,
        )

        mock_db.insert_one.return_value = MagicMock(inserted_id="x")

        result = record_delivery(
            delivery_id="del-001",
            event="task.completed",
            source_service="c9s_agentic_team",
            schema_version="1.0",
            event_id="evt-001",
            status="processed",
            idea_id="idea-1",
            feature_id="feat-1",
            issue_key="PROJ-42",
            payload={"event": "task.completed"},
            result={"status": "processed"},
        )

        assert result is True
        mock_db.insert_one.assert_called_once()
        doc = mock_db.insert_one.call_args[0][0]
        assert doc["delivery_id"] == "del-001"
        assert doc["event"] == "task.completed"
        assert doc["idea_id"] == "idea-1"
        assert doc["feature_id"] == "feat-1"
        assert doc["issue_key"] == "PROJ-42"
        assert doc["source_service"] == "c9s_agentic_team"
        assert doc["schema_version"] == "1.0"
        assert doc["received_at"] is not None

    def test_duplicate_returns_false(self, mock_db):
        from crewai_productfeature_planner.mongodb.webhook_deliveries.repository import (
            record_delivery,
        )

        mock_db.insert_one.side_effect = DuplicateKeyError("dup")

        result = record_delivery(
            delivery_id="dup-001",
            event="task.completed",
        )

        assert result is False

    def test_pymongo_error_returns_false(self, mock_db):
        from crewai_productfeature_planner.mongodb.webhook_deliveries.repository import (
            record_delivery,
        )

        mock_db.insert_one.side_effect = PyMongoError("conn failed")

        result = record_delivery(
            delivery_id="err-001",
            event="task.failed",
        )

        assert result is False


# ── has_delivery ──────────────────────────────────────────────


class TestHasDelivery:
    """Test has_delivery idempotency check."""

    def test_returns_true_when_exists(self, mock_db):
        from crewai_productfeature_planner.mongodb.webhook_deliveries.repository import (
            has_delivery,
        )

        mock_db.count_documents.return_value = 1
        assert has_delivery("exists-001") is True
        mock_db.count_documents.assert_called_once_with(
            {"delivery_id": "exists-001"}, limit=1,
        )

    def test_returns_false_when_not_exists(self, mock_db):
        from crewai_productfeature_planner.mongodb.webhook_deliveries.repository import (
            has_delivery,
        )

        mock_db.count_documents.return_value = 0
        assert has_delivery("new-001") is False

    def test_returns_false_on_error(self, mock_db):
        from crewai_productfeature_planner.mongodb.webhook_deliveries.repository import (
            has_delivery,
        )

        mock_db.count_documents.side_effect = PyMongoError("timeout")
        assert has_delivery("err-001") is False


# ── get_delivery ──────────────────────────────────────────────


class TestGetDelivery:
    """Test get_delivery retrieval."""

    def test_returns_document(self, mock_db):
        from crewai_productfeature_planner.mongodb.webhook_deliveries.repository import (
            get_delivery,
        )

        mock_db.find_one.return_value = {
            "delivery_id": "get-001",
            "event": "task.completed",
        }
        result = get_delivery("get-001")
        assert result is not None
        assert result["delivery_id"] == "get-001"

    def test_returns_none_when_not_found(self, mock_db):
        from crewai_productfeature_planner.mongodb.webhook_deliveries.repository import (
            get_delivery,
        )

        mock_db.find_one.return_value = None
        assert get_delivery("missing") is None

    def test_returns_none_on_error(self, mock_db):
        from crewai_productfeature_planner.mongodb.webhook_deliveries.repository import (
            get_delivery,
        )

        mock_db.find_one.side_effect = PyMongoError("err")
        assert get_delivery("err-001") is None


# ── list_deliveries ───────────────────────────────────────────


class TestListDeliveries:
    """Test list_deliveries with filters and pagination."""

    def test_returns_paginated_results(self, mock_db):
        from crewai_productfeature_planner.mongodb.webhook_deliveries.repository import (
            list_deliveries,
        )

        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.__iter__ = MagicMock(
            return_value=iter([{"delivery_id": "d1"}, {"delivery_id": "d2"}])
        )
        mock_db.find.return_value = mock_cursor
        mock_db.count_documents.return_value = 2

        result = list_deliveries(page=1, page_size=50)
        assert result["total"] == 2
        assert len(result["items"]) == 2
        assert result["page"] == 1
        assert result["page_size"] == 50

    def test_applies_event_filter(self, mock_db):
        from crewai_productfeature_planner.mongodb.webhook_deliveries.repository import (
            list_deliveries,
        )

        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.__iter__ = MagicMock(return_value=iter([]))
        mock_db.find.return_value = mock_cursor
        mock_db.count_documents.return_value = 0

        list_deliveries(event="task.completed")

        # Verify filter was passed
        call_args = mock_db.count_documents.call_args[0][0]
        assert call_args["event"] == "task.completed"

    def test_applies_idea_id_filter(self, mock_db):
        from crewai_productfeature_planner.mongodb.webhook_deliveries.repository import (
            list_deliveries,
        )

        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.__iter__ = MagicMock(return_value=iter([]))
        mock_db.find.return_value = mock_cursor
        mock_db.count_documents.return_value = 0

        list_deliveries(idea_id="test-idea")

        call_args = mock_db.count_documents.call_args[0][0]
        assert call_args["idea_id"] == "test-idea"

    def test_returns_empty_on_error(self, mock_db):
        from crewai_productfeature_planner.mongodb.webhook_deliveries.repository import (
            list_deliveries,
        )

        mock_db.count_documents.side_effect = PyMongoError("timeout")

        result = list_deliveries()
        assert result["items"] == []
        assert result["total"] == 0
