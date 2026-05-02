"""Tests for the Ideas CRUD router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app
from crewai_productfeature_planner.apis.ideas.models import idea_fields

_PKG = "crewai_productfeature_planner.apis.ideas.router"
_QUERIES = "crewai_productfeature_planner.mongodb.working_ideas._queries"
_STATUS = "crewai_productfeature_planner.mongodb.working_ideas._status"
_ASYNC_CLIENT = "crewai_productfeature_planner.mongodb.async_client"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _make_idea_doc(**overrides):
    doc = {
        "run_id": "run001",
        "idea": "Build a fitness tracker",
        "finalized_idea": "",
        "status": "inprogress",
        "project_id": "proj1",
        "created_at": "2026-01-01T00:00:00Z",
        "completed_at": "",
        "section": {},
        "executive_summary": [],
        "jira_phase": "",
        "ux_design_status": "",
    }
    doc.update(overrides)
    return doc


# ── GET /ideas (list, paginated) ─────────────────────────────


class TestListIdeas:
    def _mock_collection(self, docs, total=None):
        if total is None:
            total = len(docs)
        coll = MagicMock()
        coll.count_documents = AsyncMock(return_value=total)
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.skip.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.to_list = AsyncMock(return_value=list(docs))
        coll.find.return_value = cursor
        return coll

    def test_empty_list(self, client):
        coll = self._mock_collection([], total=0)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []
        assert body["page"] == 1

    def test_with_items(self, client):
        docs = [_make_idea_doc(run_id=f"r{i}") for i in range(3)]
        coll = self._mock_collection(docs, total=3)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3

    def test_page_size_25(self, client):
        coll = self._mock_collection([], total=0)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas?page_size=25")
        assert resp.status_code == 200
        assert resp.json()["page_size"] == 25

    def test_page_size_50(self, client):
        coll = self._mock_collection([], total=0)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas?page_size=50")
        assert resp.status_code == 200
        assert resp.json()["page_size"] == 50

    def test_invalid_page_size(self, client):
        resp = client.get("/ideas?page_size=0")
        assert resp.status_code == 422
        resp = client.get("/ideas?page_size=101")
        assert resp.status_code == 422

    def test_invalid_status(self, client):
        resp = client.get("/ideas?status=bogus")
        assert resp.status_code == 400
        assert "status" in resp.json()["detail"]

    def test_filter_by_project(self, client):
        coll = self._mock_collection([], total=0)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas?project_id=proj1")
        assert resp.status_code == 200
        # Default behaviour: terminal-state ideas (including completed/PRD-generated)
        # are excluded unless explicitly requested via ?status= or ?include_archived=true.
        coll.count_documents.assert_awaited_once_with(
            {"project_id": "proj1", "status": {"$nin": ["deleted", "archived", "failed", "completed"]}}
        )

    def test_filter_by_status(self, client):
        coll = self._mock_collection([], total=0)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas?status=completed")
        assert resp.status_code == 200
        coll.count_documents.assert_awaited_once_with({"status": "completed"})

    def test_filter_by_project_and_status(self, client):
        coll = self._mock_collection([], total=0)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas?project_id=proj1&status=paused")
        assert resp.status_code == 200
        coll.count_documents.assert_awaited_once_with(
            {"project_id": "proj1", "status": "paused"}
        )

    def test_default_excludes_archived_failed_and_completed(self, client):
        """Regression: GET /ideas must hide terminal-state ideas by default.

        Without this, ideas the user has 'deleted' (archived via PATCH
        /ideas/{id}/status) reappear in the dashboard listing and the
        delete looks broken. Completed (PRD-generated) ideas are also
        excluded — they no longer need attention in the active list.
        """
        coll = self._mock_collection([], total=0)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas")
        assert resp.status_code == 200
        coll.count_documents.assert_awaited_once_with(
            {"status": {"$nin": ["deleted", "archived", "failed", "completed"]}}
        )

    def test_include_archived_opt_in(self, client):
        """include_archived=true returns the unfiltered (legacy) view."""
        coll = self._mock_collection([], total=0)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas?include_archived=true")
        assert resp.status_code == 200
        coll.count_documents.assert_awaited_once_with({})

    def test_pagination_math(self, client):
        coll = self._mock_collection([], total=51)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas?page=3&page_size=25")
        body = resp.json()
        assert body["total"] == 51
        assert body["total_pages"] == 3
        assert body["page"] == 3

    def test_ux_design_status_null_in_db(self, client):
        """Regression: ux_design_status=None in MongoDB must not crash."""
        docs = [_make_idea_doc(ux_design_status=None)]
        coll = self._mock_collection(docs, total=1)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas")
        assert resp.status_code == 200
        assert resp.json()["items"][0]["ux_design_status"] == ""

    def test_page_zero_rejected(self, client):
        resp = client.get("/ideas?page=0")
        assert resp.status_code == 422


# ── GET /ideas/{run_id} ──────────────────────────────────────


class TestGetIdea:
    def test_found(self, client):
        doc = _make_idea_doc()
        with patch(
            f"{_QUERIES}.find_run_any_status",
            return_value=doc,
        ):
            resp = client.get("/ideas/run001")
        assert resp.status_code == 200
        assert resp.json()["run_id"] == "run001"
        assert resp.json()["idea"] == "Build a fitness tracker"

    def test_not_found(self, client):
        with patch(
            f"{_QUERIES}.find_run_any_status",
            return_value=None,
        ):
            resp = client.get("/ideas/nonexistent")
        assert resp.status_code == 404

    def test_completed_has_all_sections(self, client):
        doc = _make_idea_doc(status="completed")
        with patch(
            f"{_QUERIES}.find_run_any_status",
            return_value=doc,
        ):
            resp = client.get("/ideas/run001")
        body = resp.json()
        assert body["sections_done"] == 12
        assert body["total_sections"] == 12


# ── PATCH /ideas/{run_id}/status ─────────────────────────────


class TestUpdateIdeaStatus:
    def test_archive(self, client):
        doc = _make_idea_doc()
        archived = _make_idea_doc(status="archived")
        with (
            patch(
                f"{_QUERIES}.find_run_any_status",
                side_effect=[doc, archived],
            ),
            patch(
                f"{_STATUS}.mark_archived",
            ) as mock_archive,
            patch(
                "crewai_productfeature_planner.apis.ideas.patch_idea_status."
                "response_cache"
            ) as mock_cache,
        ):
            resp = client.patch(
                "/ideas/run001/status", json={"status": "archived"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"
        mock_archive.assert_called_once_with("run001")
        # Regression: PATCH must invalidate the GET /ideas list cache
        # so the just-archived idea disappears immediately.
        mock_cache.invalidate.assert_called_once_with("ideas")

    def test_pause(self, client):
        doc = _make_idea_doc()
        paused = _make_idea_doc(status="paused")
        with (
            patch(
                f"{_QUERIES}.find_run_any_status",
                side_effect=[doc, paused],
            ),
            patch(
                f"{_STATUS}.mark_paused",
            ) as mock_pause,
        ):
            resp = client.patch(
                "/ideas/run001/status", json={"status": "paused"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"
        mock_pause.assert_called_once_with("run001")

    def test_not_found(self, client):
        with patch(
            f"{_QUERIES}.find_run_any_status",
            return_value=None,
        ):
            resp = client.patch(
                "/ideas/nonexistent/status", json={"status": "archived"}
            )
        assert resp.status_code == 404


# ── DELETE /ideas/{run_id} (soft delete) ─────────────────────


class TestDeleteIdea:
    def test_soft_delete(self, client):
        doc = _make_idea_doc(status="completed")
        with (
            patch(
                f"{_QUERIES}.find_run_any_status",
                return_value=doc,
            ),
            patch(f"{_STATUS}.mark_deleted") as mock_delete,
            patch(
                "crewai_productfeature_planner.apis.ideas.delete_idea."
                "response_cache"
            ) as mock_cache,
            patch(
                "crewai_productfeature_planner.apis.ideas.delete_idea."
                "_cascade_ideation_session", return_value="",
            ),
            patch(
                "crewai_productfeature_planner.apis.ideas.delete_idea."
                "_cascade_product_requirements",
                return_value={"jira_cleared": 0, "confluence_cleared": 0},
            ),
            patch(
                "crewai_productfeature_planner.apis.ideas.delete_idea."
                "_clear_ux_state", return_value=0,
            ),
            patch(
                "crewai_productfeature_planner.apis.ideas.delete_idea."
                "_broadcast_idea_deleted",
            ),
        ):
            resp = client.delete("/ideas/run001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "deleted"
        assert body["run_id"] == "run001"
        mock_delete.assert_called_once_with("run001")
        # Regression: list cache must be invalidated so the deleted
        # idea disappears from the dashboard immediately.
        mock_cache.invalidate.assert_called_once_with("ideas")

    def test_not_found(self, client):
        with patch(
            f"{_QUERIES}.find_run_any_status",
            return_value=None,
        ):
            resp = client.delete("/ideas/nonexistent")
        assert resp.status_code == 404

    def test_inprogress_returns_409(self, client):
        """Regression: in-flight ideas must not be deleted — user must pause first."""
        doc = _make_idea_doc(status="inprogress")
        with patch(f"{_QUERIES}.find_run_any_status", return_value=doc):
            resp = client.delete("/ideas/run001")
        assert resp.status_code == 409

    def test_default_listing_excludes_deleted(self, client):
        """Regression: GET /ideas must hide soft-deleted rows by default."""
        coll = MagicMock()
        coll.count_documents = AsyncMock(return_value=0)
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.skip.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.to_list = AsyncMock(return_value=[])
        coll.find.return_value = cursor
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas")
        assert resp.status_code == 200
        coll.count_documents.assert_awaited_once_with(
            {"status": {"$nin": ["deleted", "archived", "failed", "completed"]}}
        )

    def test_invalid_status(self, client):
        resp = client.patch(
            "/ideas/run001/status", json={"status": "completed"}
        )
        assert resp.status_code == 422


# ── idea_fields unit tests ───────────────────────────────────


class TestIdeaFieldsUxDesignStatus:
    """Regression: ux_design_status must never return None."""

    def test_both_fields_none(self):
        doc = _make_idea_doc(ux_design_status=None)
        doc["figma_design_status"] = None
        assert idea_fields(doc)["ux_design_status"] == ""

    def test_ux_none_figma_missing(self):
        doc = _make_idea_doc(ux_design_status=None)
        assert idea_fields(doc)["ux_design_status"] == ""

    def test_ux_none_figma_set(self):
        doc = _make_idea_doc(ux_design_status=None)
        doc["figma_design_status"] = "completed"
        assert idea_fields(doc)["ux_design_status"] == "completed"

    def test_ux_empty_figma_none(self):
        doc = _make_idea_doc(ux_design_status="")
        doc["figma_design_status"] = None
        # "" is falsy so falls through; None is caught by trailing or ""
        assert idea_fields(doc)["ux_design_status"] == ""

    def test_ux_set(self):
        doc = _make_idea_doc(ux_design_status="generating")
        assert idea_fields(doc)["ux_design_status"] == "generating"
