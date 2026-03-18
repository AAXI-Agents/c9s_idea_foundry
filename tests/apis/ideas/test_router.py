"""Tests for the Ideas CRUD router."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app

_PKG = "crewai_productfeature_planner.apis.ideas.router"
_QUERIES = "crewai_productfeature_planner.mongodb.working_ideas._queries"
_STATUS = "crewai_productfeature_planner.mongodb.working_ideas._status"
_CLIENT = "crewai_productfeature_planner.mongodb.working_ideas._common"


@pytest.fixture()
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
        "figma_design_url": "",
        "figma_design_status": "",
    }
    doc.update(overrides)
    return doc


# ── GET /ideas (list, paginated) ─────────────────────────────


class TestListIdeas:
    def _mock_collection(self, docs, total=None):
        if total is None:
            total = len(docs)
        coll = MagicMock()
        coll.count_documents.return_value = total
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.skip.return_value = cursor
        cursor.limit.return_value = list(docs)
        coll.find.return_value = cursor
        return coll

    def test_empty_list(self, client):
        coll = self._mock_collection([], total=0)
        with patch(f"{_CLIENT}.get_db") as mock_db:
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
        with patch(f"{_CLIENT}.get_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3

    def test_page_size_25(self, client):
        coll = self._mock_collection([], total=0)
        with patch(f"{_CLIENT}.get_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas?page_size=25")
        assert resp.status_code == 200
        assert resp.json()["page_size"] == 25

    def test_page_size_50(self, client):
        coll = self._mock_collection([], total=0)
        with patch(f"{_CLIENT}.get_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas?page_size=50")
        assert resp.status_code == 200
        assert resp.json()["page_size"] == 50

    def test_invalid_page_size(self, client):
        resp = client.get("/ideas?page_size=15")
        assert resp.status_code == 400
        assert "page_size" in resp.json()["detail"]

    def test_invalid_status(self, client):
        resp = client.get("/ideas?status=bogus")
        assert resp.status_code == 400
        assert "status" in resp.json()["detail"]

    def test_filter_by_project(self, client):
        coll = self._mock_collection([], total=0)
        with patch(f"{_CLIENT}.get_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas?project_id=proj1")
        assert resp.status_code == 200
        # Verify the query included project_id filter
        coll.count_documents.assert_called_once_with({"project_id": "proj1"})

    def test_filter_by_status(self, client):
        coll = self._mock_collection([], total=0)
        with patch(f"{_CLIENT}.get_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas?status=completed")
        assert resp.status_code == 200
        coll.count_documents.assert_called_once_with({"status": "completed"})

    def test_filter_by_project_and_status(self, client):
        coll = self._mock_collection([], total=0)
        with patch(f"{_CLIENT}.get_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas?project_id=proj1&status=paused")
        assert resp.status_code == 200
        coll.count_documents.assert_called_once_with(
            {"project_id": "proj1", "status": "paused"}
        )

    def test_pagination_math(self, client):
        coll = self._mock_collection([], total=51)
        with patch(f"{_CLIENT}.get_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/ideas?page=3&page_size=25")
        body = resp.json()
        assert body["total"] == 51
        assert body["total_pages"] == 3
        assert body["page"] == 3

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
        ):
            resp = client.patch(
                "/ideas/run001/status", json={"status": "archived"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"
        mock_archive.assert_called_once_with("run001")

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

    def test_invalid_status(self, client):
        resp = client.patch(
            "/ideas/run001/status", json={"status": "completed"}
        )
        assert resp.status_code == 422
