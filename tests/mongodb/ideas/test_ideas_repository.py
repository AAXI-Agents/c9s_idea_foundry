"""Tests for the ``ideas`` MongoDB repository.

Follows the same pattern as ``tests/mongodb/test_ideation_sessions.py``:
patching ``get_db`` to return a fresh mock and verifying CRUD calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.ideas import repository as ideas_repo


# ── helpers ───────────────────────────────────────────────────


def _make_mock_db(*, find_one_return=None, modified_count=1):
    """Create a mock DB whose ``ideas`` collection returns sane defaults."""
    mock_db = MagicMock()
    col = mock_db.__getitem__.return_value
    col.find_one.return_value = find_one_return
    col.insert_one.return_value = MagicMock(inserted_id="abc")
    col.update_one.return_value = MagicMock(modified_count=modified_count)
    col.count_documents.return_value = 0
    col.find.return_value.sort.return_value.skip.return_value.limit.return_value = []
    return mock_db, col


def _tenant():
    return TenantContext(
        enterprise_id="ent-1",
        organization_id="org-1",
    )


# ── create_idea ──────────────────────────────────────────────


class TestCreateIdea:
    def test_creates_document_in_draft_status(self):
        mock_db, col = _make_mock_db()
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            doc = ideas_repo.create_idea(
                project_id="proj-1",
                title="Test Idea",
                description="A test",
                created_by="user-1",
                tenant=_tenant(),
            )

        assert doc is not None
        assert doc["title"] == "Test Idea"
        assert doc["status"] == "draft"
        assert doc["project_id"] == "proj-1"
        assert doc["created_by"] == "user-1"
        assert doc["features"] == []
        assert doc["overall_completion"] == 0.0
        assert doc["active_run_id"] is None
        assert doc["run_ids"] == []
        assert doc["organization_id"] == "org-1"
        assert doc["enterprise_id"] == "ent-1"
        col.insert_one.assert_called_once()

    def test_creates_with_ideation_session_link(self):
        mock_db, col = _make_mock_db()
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            doc = ideas_repo.create_idea(
                project_id="proj-1",
                title="From Session",
                created_by="user-1",
                ideation_session_id="session-abc",
                tenant=_tenant(),
            )

        assert doc is not None
        assert doc["ideation_session_id"] == "session-abc"

    def test_creates_with_features(self):
        features = [{"id": "f1", "name": "Auth", "description": "Login flow"}]
        mock_db, col = _make_mock_db()
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            doc = ideas_repo.create_idea(
                project_id="proj-1",
                title="With Features",
                created_by="user-1",
                features=features,
                tenant=_tenant(),
            )

        assert doc is not None
        assert len(doc["features"]) == 1
        assert doc["features"][0]["name"] == "Auth"

    def test_returns_none_on_pymongo_error(self):
        mock_db, col = _make_mock_db()
        from pymongo.errors import PyMongoError
        col.insert_one.side_effect = PyMongoError("insert failed")
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            doc = ideas_repo.create_idea(
                project_id="proj-1",
                title="Fail",
                created_by="user-1",
                tenant=_tenant(),
            )
        assert doc is None


# ── get_idea ─────────────────────────────────────────────────


class TestGetIdea:
    def test_returns_document(self):
        expected = {"idea_id": "id-1", "title": "Found"}
        mock_db, col = _make_mock_db(find_one_return=expected)
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            doc = ideas_repo.get_idea(idea_id="id-1", tenant=_tenant())
        assert doc == expected

    def test_returns_none_when_not_found(self):
        mock_db, col = _make_mock_db(find_one_return=None)
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            doc = ideas_repo.get_idea(idea_id="missing", tenant=_tenant())
        assert doc is None


# ── update_idea ──────────────────────────────────────────────


class TestUpdateIdea:
    def test_updates_title(self):
        updated = {"idea_id": "id-1", "title": "Updated"}
        mock_db, col = _make_mock_db(find_one_return=updated)
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            doc = ideas_repo.update_idea(
                idea_id="id-1",
                title="Updated",
                tenant=_tenant(),
            )
        assert doc is not None
        col.update_one.assert_called_once()

    def test_noop_when_nothing_to_update(self):
        existing = {"idea_id": "id-1", "title": "Same"}
        mock_db, col = _make_mock_db(find_one_return=existing)
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            doc = ideas_repo.update_idea(
                idea_id="id-1",
                tenant=_tenant(),
            )
        assert doc is not None
        col.update_one.assert_not_called()


# ── update_idea_status ───────────────────────────────────────


class TestUpdateIdeaStatus:
    def test_valid_status_transition(self):
        mock_db, col = _make_mock_db()
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            ok = ideas_repo.update_idea_status(
                idea_id="id-1",
                status="active",
                tenant=_tenant(),
            )
        assert ok is True
        col.update_one.assert_called_once()

    def test_invalid_status_rejected(self):
        mock_db, col = _make_mock_db()
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            ok = ideas_repo.update_idea_status(
                idea_id="id-1",
                status="invalid_status",
                tenant=_tenant(),
            )
        assert ok is False
        col.update_one.assert_not_called()

    def test_returns_false_when_no_match(self):
        mock_db, col = _make_mock_db(modified_count=0)
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            ok = ideas_repo.update_idea_status(
                idea_id="missing",
                status="active",
                tenant=_tenant(),
            )
        assert ok is False


# ── set_active_run ───────────────────────────────────────────


class TestSetActiveRun:
    def test_sets_run_id(self):
        mock_db, col = _make_mock_db()
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            ok = ideas_repo.set_active_run(
                idea_id="id-1",
                run_id="run-abc",
                tenant=_tenant(),
            )
        assert ok is True
        call_args = col.update_one.call_args
        update_doc = call_args[0][1]
        assert update_doc["$set"]["active_run_id"] == "run-abc"
        assert update_doc["$addToSet"]["run_ids"] == "run-abc"


# ── update_features ──────────────────────────────────────────


class TestUpdateFeatures:
    def test_replaces_features_array(self):
        features = [{"id": "f1", "name": "Search"}]
        mock_db, col = _make_mock_db()
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            ok = ideas_repo.update_features(
                idea_id="id-1",
                features=features,
                tenant=_tenant(),
            )
        assert ok is True


# ── update_overall_completion ────────────────────────────────


class TestUpdateOverallCompletion:
    def test_clamps_to_0_100(self):
        mock_db, col = _make_mock_db()
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            ideas_repo.update_overall_completion(
                idea_id="id-1",
                overall_completion=150.0,
                tenant=_tenant(),
            )
        call_args = col.update_one.call_args
        assert call_args[0][1]["$set"]["overall_completion"] == 100.0

    def test_clamps_negative_to_zero(self):
        mock_db, col = _make_mock_db()
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            ideas_repo.update_overall_completion(
                idea_id="id-1",
                overall_completion=-10.0,
                tenant=_tenant(),
            )
        call_args = col.update_one.call_args
        assert call_args[0][1]["$set"]["overall_completion"] == 0.0


# ── save_design_url ──────────────────────────────────────────


class TestSaveDesignUrl:
    def test_saves_url_and_type(self):
        mock_db, col = _make_mock_db()
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            ok = ideas_repo.save_design_url(
                idea_id="id-1",
                design_url="https://figma.com/file/abc",
                design_url_type="figma",
                tenant=_tenant(),
            )
        assert ok is True
        call_args = col.update_one.call_args
        assert call_args[0][1]["$set"]["design_url"] == "https://figma.com/file/abc"
        assert call_args[0][1]["$set"]["design_url_type"] == "figma"


# ── delete_idea ──────────────────────────────────────────────


class TestDeleteIdea:
    def test_deletes_draft_idea(self):
        draft_doc = {"idea_id": "id-1", "status": "draft"}
        mock_db, col = _make_mock_db(find_one_return=draft_doc)
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            ok = ideas_repo.delete_idea(idea_id="id-1", tenant=_tenant())
        assert ok is True

    def test_rejects_non_draft_idea(self):
        active_doc = {"idea_id": "id-1", "status": "active"}
        mock_db, col = _make_mock_db(find_one_return=active_doc)
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            ok = ideas_repo.delete_idea(idea_id="id-1", tenant=_tenant())
        assert ok is False

    def test_returns_false_when_not_found(self):
        mock_db, col = _make_mock_db(find_one_return=None)
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            ok = ideas_repo.delete_idea(idea_id="missing", tenant=_tenant())
        assert ok is False


# ── list_ideas ───────────────────────────────────────────────


class TestListIdeas:
    def test_returns_list(self):
        docs = [{"idea_id": "a"}, {"idea_id": "b"}]
        mock_db, col = _make_mock_db()
        col.find.return_value.sort.return_value.skip.return_value.limit.return_value = docs
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            result = ideas_repo.list_ideas(
                project_id="proj-1",
                tenant=_tenant(),
            )
        assert len(result) == 2

    def test_excludes_archived_by_default(self):
        mock_db, col = _make_mock_db()
        col.find.return_value.sort.return_value.skip.return_value.limit.return_value = []
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            ideas_repo.list_ideas(project_id="proj-1", tenant=_tenant())
        query = col.find.call_args[0][0]
        assert query["status"] == {"$ne": "archived"}

    def test_explicit_status_filter(self):
        mock_db, col = _make_mock_db()
        col.find.return_value.sort.return_value.skip.return_value.limit.return_value = []
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            ideas_repo.list_ideas(
                project_id="proj-1",
                status="completed",
                tenant=_tenant(),
            )
        query = col.find.call_args[0][0]
        assert query["status"] == "completed"

    def test_deduplicates_by_idea_id(self):
        """Defensive dedup: if DB returns duplicates, only first is kept."""
        docs = [
            {"idea_id": "dup-1", "title": "First"},
            {"idea_id": "dup-1", "title": "Second (dup)"},
            {"idea_id": "unique-2", "title": "Unique"},
        ]
        mock_db, col = _make_mock_db()
        col.find.return_value.sort.return_value.skip.return_value.limit.return_value = docs
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            result = ideas_repo.list_ideas(
                project_id="proj-1",
                tenant=_tenant(),
            )
        assert len(result) == 2
        assert result[0]["idea_id"] == "dup-1"
        assert result[0]["title"] == "First"
        assert result[1]["idea_id"] == "unique-2"


# ── find_idea_by_session ─────────────────────────────────────


class TestFindIdeaBySession:
    def test_returns_existing_idea(self):
        expected = {"idea_id": "id-1", "ideation_session_id": "ses-1"}
        mock_db, col = _make_mock_db(find_one_return=expected)
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            doc = ideas_repo.find_idea_by_session(
                session_id="ses-1", tenant=_tenant()
            )
        assert doc == expected
        query = col.find_one.call_args[0][0]
        assert query["ideation_session_id"] == "ses-1"

    def test_returns_none_when_not_found(self):
        mock_db, col = _make_mock_db(find_one_return=None)
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            doc = ideas_repo.find_idea_by_session(
                session_id="missing", tenant=_tenant()
            )
        assert doc is None

    def test_returns_none_on_pymongo_error(self):
        mock_db, col = _make_mock_db()
        from pymongo.errors import PyMongoError
        col.find_one.side_effect = PyMongoError("query failed")
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            doc = ideas_repo.find_idea_by_session(
                session_id="ses-1", tenant=_tenant()
            )
        assert doc is None


# ── count_ideas ──────────────────────────────────────────────


class TestCountIdeas:
    def test_counts_non_archived(self):
        mock_db, col = _make_mock_db()
        col.count_documents.return_value = 5
        with patch.object(ideas_repo, "get_db", return_value=mock_db):
            count = ideas_repo.count_ideas(project_id="proj-1", tenant=_tenant())
        assert count == 5
