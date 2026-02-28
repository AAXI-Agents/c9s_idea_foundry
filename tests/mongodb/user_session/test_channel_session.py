"""Tests for user_session channel session CRUD functions."""

from unittest.mock import MagicMock, patch

import pytest

_US_MODULE = "crewai_productfeature_planner.mongodb.user_session"


@pytest.fixture
def mock_db():
    """Provide a mock MongoDB database."""
    with patch(f"{_US_MODULE}.get_db") as mock_get_db:
        db = MagicMock()
        mock_get_db.return_value = db
        yield db


class TestStartChannelSession:
    def test_creates_document(self, mock_db):
        from crewai_productfeature_planner.mongodb.user_session import (
            start_channel_session,
        )

        collection = MagicMock()
        mock_db.__getitem__.return_value = collection
        # end_channel_session is called first — returns no match
        collection.update_one.return_value = MagicMock(modified_count=0)

        sid = start_channel_session(
            channel_id="C1",
            project_id="p1",
            project_name="Test Project",
            activated_by="U_ADMIN",
        )

        assert sid is not None
        assert len(sid) == 32  # UUID hex
        insert_call = collection.insert_one.call_args
        doc = insert_call[0][0]
        assert doc["context_type"] == "channel"
        assert doc["channel"] == "C1"
        assert doc["project_id"] == "p1"
        assert doc["activated_by"] == "U_ADMIN"
        assert doc["active"] is True

    def test_failure_returns_none(self, mock_db):
        from pymongo.errors import PyMongoError

        from crewai_productfeature_planner.mongodb.user_session import (
            start_channel_session,
        )

        collection = MagicMock()
        mock_db.__getitem__.return_value = collection
        collection.update_one.return_value = MagicMock(modified_count=0)
        collection.insert_one.side_effect = PyMongoError("fail")

        sid = start_channel_session(
            channel_id="C1",
            project_id="p1",
            project_name="Fail",
            activated_by="U1",
        )

        assert sid is None


class TestEndChannelSession:
    def test_ends_active_session(self, mock_db):
        from crewai_productfeature_planner.mongodb.user_session import (
            end_channel_session,
        )

        collection = MagicMock()
        mock_db.__getitem__.return_value = collection
        collection.update_one.return_value = MagicMock(modified_count=1)

        count = end_channel_session(channel_id="C1")

        assert count == 1
        update_call = collection.update_one.call_args
        query = update_call[0][0]
        assert query["channel"] == "C1"
        assert query["context_type"] == "channel"
        assert query["active"] is True

    def test_no_active_session(self, mock_db):
        from crewai_productfeature_planner.mongodb.user_session import (
            end_channel_session,
        )

        collection = MagicMock()
        mock_db.__getitem__.return_value = collection
        collection.update_one.return_value = MagicMock(modified_count=0)

        count = end_channel_session(channel_id="C999")
        assert count == 0


class TestGetActiveChannelSession:
    def test_found(self, mock_db):
        from crewai_productfeature_planner.mongodb.user_session import (
            get_active_channel_session,
        )

        collection = MagicMock()
        mock_db.__getitem__.return_value = collection
        collection.find_one.return_value = {
            "channel": "C1",
            "project_id": "p1",
            "active": True,
        }

        result = get_active_channel_session("C1")
        assert result["project_id"] == "p1"
        find_call = collection.find_one.call_args
        query = find_call[0][0]
        assert query["channel"] == "C1"
        assert query["context_type"] == "channel"

    def test_not_found(self, mock_db):
        from crewai_productfeature_planner.mongodb.user_session import (
            get_active_channel_session,
        )

        collection = MagicMock()
        mock_db.__getitem__.return_value = collection
        collection.find_one.return_value = None

        assert get_active_channel_session("C999") is None

    def test_error(self, mock_db):
        from pymongo.errors import PyMongoError

        from crewai_productfeature_planner.mongodb.user_session import (
            get_active_channel_session,
        )

        collection = MagicMock()
        mock_db.__getitem__.return_value = collection
        collection.find_one.side_effect = PyMongoError("fail")

        assert get_active_channel_session("C1") is None
