"""Tests for the Projects CRUD router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app

_PKG = "crewai_productfeature_planner.apis.projects.router"
_REPO = "crewai_productfeature_planner.mongodb.project_config.repository"
_ASYNC_CLIENT = "crewai_productfeature_planner.mongodb.async_client"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _make_project_doc(**overrides):
    doc = {
        "project_id": "abc123",
        "name": "Test Project",
        "confluence_space_key": "TP",
        "jira_project_key": "TP",
        "confluence_parent_id": "",
        "reference_urls": [],
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    doc.update(overrides)
    return doc


# ── GET /projects (list, paginated) ──────────────────────────


class TestListProjects:
    def _mock_collection(self, docs, total=None):
        """Build a mock Motor-compatible async collection."""
        if total is None:
            total = len(docs)
        coll = MagicMock()
        coll.count_documents = AsyncMock(return_value=total)
        coll.estimated_document_count = AsyncMock(return_value=total)
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
            resp = client.get("/projects")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []
        assert body["page"] == 1
        assert body["total_pages"] == 1

    def test_default_page_size(self, client):
        docs = [_make_project_doc(project_id=f"p{i}") for i in range(3)]
        coll = self._mock_collection(docs, total=3)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/projects")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3
        assert body["page_size"] == 10

    def test_page_size_25(self, client):
        coll = self._mock_collection([], total=0)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/projects?page_size=25")
        assert resp.status_code == 200
        assert resp.json()["page_size"] == 25

    def test_page_size_50(self, client):
        coll = self._mock_collection([], total=0)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/projects?page_size=50")
        assert resp.status_code == 200
        assert resp.json()["page_size"] == 50

    def test_invalid_page_size(self, client):
        resp = client.get("/projects?page_size=15")
        assert resp.status_code == 400
        assert "page_size" in resp.json()["detail"]

    def test_pagination_math(self, client):
        """total_pages is ceil(total / page_size)."""
        coll = self._mock_collection([], total=26)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/projects?page=2&page_size=10")
        body = resp.json()
        assert body["total"] == 26
        assert body["total_pages"] == 3
        assert body["page"] == 2

    def test_page_zero_rejected(self, client):
        resp = client.get("/projects?page=0")
        assert resp.status_code == 422  # FastAPI validation (ge=1)


# ── GET /projects/{project_id} ───────────────────────────────


class TestGetProject:
    def test_found(self, client):
        doc = _make_project_doc()
        with patch(
            f"{_REPO}.get_project",
            return_value=doc,
        ):
            resp = client.get("/projects/abc123")
        assert resp.status_code == 200
        assert resp.json()["project_id"] == "abc123"
        assert resp.json()["name"] == "Test Project"

    def test_not_found(self, client):
        with patch(
            f"{_REPO}.get_project",
            return_value=None,
        ):
            resp = client.get("/projects/nonexistent")
        assert resp.status_code == 404


# ── POST /projects ───────────────────────────────────────────


class TestCreateProject:
    def test_success(self, client):
        doc = _make_project_doc()
        with (
            patch(
                f"{_REPO}.create_project",
                return_value="abc123",
            ),
            patch(
                f"{_REPO}.get_project",
                return_value=doc,
            ),
        ):
            resp = client.post("/projects", json={"name": "Test Project"})
        assert resp.status_code == 201
        assert resp.json()["project_id"] == "abc123"

    def test_empty_name_rejected(self, client):
        resp = client.post("/projects", json={"name": ""})
        assert resp.status_code == 422

    def test_create_failure(self, client):
        with patch(
            f"{_REPO}.create_project",
            return_value=None,
        ):
            resp = client.post("/projects", json={"name": "Fail"})
        assert resp.status_code == 500


# ── PATCH /projects/{project_id} ─────────────────────────────


class TestUpdateProject:
    def test_success(self, client):
        doc = _make_project_doc()
        updated = _make_project_doc(name="Updated")
        with (
            patch(
                f"{_REPO}.get_project",
                side_effect=[doc, updated],
            ),
            patch(
                f"{_REPO}.update_project",
            ),
        ):
            resp = client.patch("/projects/abc123", json={"name": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"

    def test_not_found(self, client):
        with patch(
            f"{_REPO}.get_project",
            return_value=None,
        ):
            resp = client.patch("/projects/nonexistent", json={"name": "X"})
        assert resp.status_code == 404

    def test_no_op_update(self, client):
        """PATCH with empty body still returns the project."""
        doc = _make_project_doc()
        with (
            patch(
                f"{_REPO}.get_project",
                side_effect=[doc, doc],
            ),
        ):
            resp = client.patch("/projects/abc123", json={})
        assert resp.status_code == 200


# ── DELETE /projects/{project_id} ────────────────────────────


class TestDeleteProject:
    def test_success(self, client):
        doc = _make_project_doc()
        with (
            patch(
                f"{_REPO}.get_project",
                return_value=doc,
            ),
            patch(
                f"{_REPO}.delete_project",
            ),
        ):
            resp = client.delete("/projects/abc123")
        assert resp.status_code == 204

    def test_not_found(self, client):
        with patch(
            f"{_REPO}.get_project",
            return_value=None,
        ):
            resp = client.delete("/projects/nonexistent")
        assert resp.status_code == 404
