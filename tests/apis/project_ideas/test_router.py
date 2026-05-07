"""Tests for the Project Ideas CRUD router.

Routes under: /projects/{project_id}/ideas/...
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app

_REPO = "crewai_productfeature_planner.apis.project_ideas._route_crud"
_FEAT_REPO = "crewai_productfeature_planner.apis.project_ideas._route_features"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _make_idea_doc(**overrides):
    doc = {
        "idea_id": "idea-001",
        "project_id": "proj-1",
        "title": "Test Idea",
        "description": "A test idea",
        "status": "draft",
        "features": [],
        "overall_completion": 0.0,
        "active_run_id": None,
        "run_ids": [],
        "ideation_session_id": None,
        "design_url": None,
        "design_url_type": None,
        "created_by": "user-1",
        "created_at": "2026-05-01T00:00:00Z",
        "updated_at": "2026-05-01T00:00:00Z",
        "organization_id": "org-1",
        "enterprise_id": "ent-1",
    }
    doc.update(overrides)
    return doc


# ── POST /projects/{project_id}/ideas ────────────────────────


class TestCreateProjectIdea:
    def test_creates_idea(self, client):
        doc = _make_idea_doc()
        with patch(f"{_REPO}.create_idea", return_value=doc):
            resp = client.post(
                "/projects/proj-1/ideas",
                json={"title": "Test Idea", "description": "A test idea"},
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["idea_id"] == "idea-001"
        assert body["title"] == "Test Idea"
        assert body["status"] == "draft"

    def test_creates_with_session_link(self, client):
        doc = _make_idea_doc(ideation_session_id="sess-abc")
        with patch(f"{_REPO}.create_idea", return_value=doc):
            resp = client.post(
                "/projects/proj-1/ideas",
                json={
                    "title": "From Session",
                    "ideation_session_id": "sess-abc",
                },
            )
        assert resp.status_code == 201
        assert resp.json()["ideation_session_id"] == "sess-abc"

    def test_rejects_empty_title(self, client):
        resp = client.post(
            "/projects/proj-1/ideas",
            json={"title": ""},
        )
        assert resp.status_code == 422

    def test_500_on_repo_failure(self, client):
        with patch(f"{_REPO}.create_idea", return_value=None):
            resp = client.post(
                "/projects/proj-1/ideas",
                json={"title": "Fail"},
            )
        assert resp.status_code == 500


# ── GET /projects/{project_id}/ideas ─────────────────────────


class TestListProjectIdeas:
    def test_empty_list(self, client):
        with (
            patch(f"{_REPO}.count_ideas", return_value=0),
            patch(f"{_REPO}.list_ideas", return_value=[]),
        ):
            resp = client.get("/projects/proj-1/ideas")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []
        assert body["page"] == 1

    def test_with_items(self, client):
        docs = [_make_idea_doc(idea_id=f"idea-{i}") for i in range(3)]
        with (
            patch(f"{_REPO}.count_ideas", return_value=3),
            patch(f"{_REPO}.list_ideas", return_value=docs),
        ):
            resp = client.get("/projects/proj-1/ideas")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3

    def test_pagination_params(self, client):
        with (
            patch(f"{_REPO}.count_ideas", return_value=0),
            patch(f"{_REPO}.list_ideas", return_value=[]),
        ):
            resp = client.get("/projects/proj-1/ideas?page=2&page_size=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 2
        assert body["page_size"] == 5

    def test_status_filter(self, client):
        with (
            patch(f"{_REPO}.count_ideas", return_value=0),
            patch(f"{_REPO}.list_ideas", return_value=[]),
        ):
            resp = client.get("/projects/proj-1/ideas?status=active")
        assert resp.status_code == 200


# ── GET /projects/{project_id}/ideas/{idea_id} ───────────────


class TestGetProjectIdea:
    def test_returns_idea(self, client):
        doc = _make_idea_doc()
        with patch(f"{_REPO}.get_idea", return_value=doc):
            resp = client.get("/projects/proj-1/ideas/idea-001")
        assert resp.status_code == 200
        assert resp.json()["idea_id"] == "idea-001"

    def test_404_not_found(self, client):
        with patch(f"{_REPO}.get_idea", return_value=None):
            resp = client.get("/projects/proj-1/ideas/missing")
        assert resp.status_code == 404

    def test_404_wrong_project(self, client):
        doc = _make_idea_doc(project_id="other-project")
        with patch(f"{_REPO}.get_idea", return_value=doc):
            resp = client.get("/projects/proj-1/ideas/idea-001")
        assert resp.status_code == 404


# ── PATCH /projects/{project_id}/ideas/{idea_id} ─────────────


class TestUpdateProjectIdea:
    def test_updates_metadata(self, client):
        existing = _make_idea_doc()
        updated = _make_idea_doc(title="Updated Title")
        with (
            patch(f"{_REPO}.get_idea", return_value=existing),
            patch(f"{_REPO}.update_idea", return_value=updated),
        ):
            resp = client.patch(
                "/projects/proj-1/ideas/idea-001",
                json={"title": "Updated Title"},
            )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    def test_404_not_found(self, client):
        with patch(f"{_REPO}.get_idea", return_value=None):
            resp = client.patch(
                "/projects/proj-1/ideas/missing",
                json={"title": "X"},
            )
        assert resp.status_code == 404


# ── PATCH /projects/{project_id}/ideas/{idea_id}/status ──────


class TestUpdateProjectIdeaStatus:
    def test_updates_status(self, client):
        existing = _make_idea_doc()
        with (
            patch(f"{_REPO}.get_idea", return_value=existing),
            patch(f"{_REPO}.update_idea_status", return_value=True),
        ):
            resp = client.patch(
                "/projects/proj-1/ideas/idea-001/status",
                json={"status": "active"},
            )
        assert resp.status_code == 204

    def test_404_not_found(self, client):
        with patch(f"{_REPO}.get_idea", return_value=None):
            resp = client.patch(
                "/projects/proj-1/ideas/missing/status",
                json={"status": "active"},
            )
        assert resp.status_code == 404

    def test_invalid_status(self, client):
        resp = client.patch(
            "/projects/proj-1/ideas/idea-001/status",
            json={"status": "invalid"},
        )
        assert resp.status_code == 422


# ── DELETE /projects/{project_id}/ideas/{idea_id} ────────────


class TestDeleteProjectIdea:
    def test_deletes_draft_idea(self, client):
        existing = _make_idea_doc(status="draft")
        with (
            patch(f"{_REPO}.get_idea", return_value=existing),
            patch(f"{_REPO}.delete_idea", return_value=True),
        ):
            resp = client.delete("/projects/proj-1/ideas/idea-001")
        assert resp.status_code == 204

    def test_rejects_non_draft(self, client):
        existing = _make_idea_doc(status="active")
        with patch(f"{_REPO}.get_idea", return_value=existing):
            resp = client.delete("/projects/proj-1/ideas/idea-001")
        assert resp.status_code == 400

    def test_404_not_found(self, client):
        with patch(f"{_REPO}.get_idea", return_value=None):
            resp = client.delete("/projects/proj-1/ideas/missing")
        assert resp.status_code == 404


# ── PATCH /projects/{project_id}/ideas/{idea_id}/features ────


class TestUpdateIdeaFeatures:
    def test_updates_features(self, client):
        existing = _make_idea_doc()
        updated = _make_idea_doc(features=[
            {"id": "f1", "name": "Auth", "description": "Login", "completion_pct": 0.0}
        ])
        with (
            patch(f"{_FEAT_REPO}.get_idea", side_effect=[existing, updated]),
            patch(f"{_FEAT_REPO}.update_features", return_value=True),
        ):
            resp = client.patch(
                "/projects/proj-1/ideas/idea-001/features",
                json={
                    "features": [
                        {"id": "f1", "name": "Auth", "description": "Login"}
                    ]
                },
            )
        assert resp.status_code == 200
        assert len(resp.json()["features"]) == 1

    def test_404_not_found(self, client):
        with patch(f"{_FEAT_REPO}.get_idea", return_value=None):
            resp = client.patch(
                "/projects/proj-1/ideas/missing/features",
                json={"features": []},
            )
        assert resp.status_code == 404
