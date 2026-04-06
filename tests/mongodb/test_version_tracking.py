"""Tests for PRD version tracking in the productRequirements repository."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

_REPO = "crewai_productfeature_planner.mongodb.product_requirements.repository"


@pytest.fixture()
def mock_db():
    """Patch get_db so we don't need a real MongoDB."""
    col = MagicMock()
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=col)
    with patch(f"{_REPO}.get_db", return_value=db):
        yield col


class TestSaveVersionSnapshot:
    """Test save_version_snapshot function."""

    def test_saves_snapshot_successfully(self, mock_db):
        from crewai_productfeature_planner.mongodb.product_requirements.repository import (
            save_version_snapshot,
        )
        mock_db.update_one.return_value = MagicMock(
            upserted_id=None, modified_count=1,
        )
        result = save_version_snapshot(
            "run1",
            version=1,
            sections_snapshot={"problem_statement": "Content v1"},
            changelog_entry="Initial version",
        )
        assert result is True
        mock_db.update_one.assert_called_once()
        call_args = mock_db.update_one.call_args
        assert call_args[0][0] == {"run_id": "run1"}
        update = call_args[0][1]
        assert "$push" in update
        assert "version_history" in update["$push"]
        assert update["$push"]["version_history"]["version"] == 1

    def test_returns_false_on_db_error(self, mock_db):
        from pymongo.errors import PyMongoError
        from crewai_productfeature_planner.mongodb.product_requirements.repository import (
            save_version_snapshot,
        )
        mock_db.update_one.side_effect = PyMongoError("connection lost")
        result = save_version_snapshot(
            "run1", version=1, sections_snapshot={},
        )
        assert result is False


class TestGetVersionHistory:
    """Test get_version_history function."""

    def test_returns_empty_when_no_record(self, mock_db):
        from crewai_productfeature_planner.mongodb.product_requirements.repository import (
            get_version_history,
        )
        mock_db.find_one.return_value = None
        assert get_version_history("run1") == []

    def test_returns_history(self, mock_db):
        from crewai_productfeature_planner.mongodb.product_requirements.repository import (
            get_version_history,
        )
        mock_db.find_one.return_value = {
            "run_id": "run1",
            "version_history": [
                {"version": 1, "sections": {"ps": "v1"}, "created_at": "2026-04-05"},
                {"version": 2, "sections": {"ps": "v2"}, "created_at": "2026-04-06"},
            ],
        }
        history = get_version_history("run1")
        assert len(history) == 2
        assert history[0]["version"] == 1


class TestGetCurrentVersion:
    """Test get_current_version function."""

    def test_returns_zero_when_no_record(self, mock_db):
        from crewai_productfeature_planner.mongodb.product_requirements.repository import (
            get_current_version,
        )
        mock_db.find_one.return_value = None
        assert get_current_version("run1") == 0

    def test_returns_version(self, mock_db):
        from crewai_productfeature_planner.mongodb.product_requirements.repository import (
            get_current_version,
        )
        mock_db.find_one.return_value = {"run_id": "run1", "current_version": 3}
        assert get_current_version("run1") == 3
