"""Tests for GET /projects/{project_id}/backlog endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app

_PKG = "crewai_productfeature_planner.apis.projects.get_backlog"
_REPO = "crewai_productfeature_planner.mongodb.project_config.repository"
# The backlog endpoint imports get_project lazily — patch at the repo level.
_GET_PROJECT = f"{_REPO}.get_project"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _mock_db(docs: list[dict]):
    """Return a mock ``get_db()`` with workingIdeas containing *docs*."""
    db = MagicMock()

    class FakeCursor:
        def __init__(self, data):
            self._data = list(data)

        def sort(self, *a, **kw):
            return self

        def limit(self, *a, **kw):
            return self

        def __iter__(self):
            return iter(self._data)

    coll = MagicMock()
    coll.find.return_value = FakeCursor(docs)
    db.__getitem__ = MagicMock(return_value=coll)
    return db


class TestProjectBacklog:
    """Tests for GET /projects/{project_id}/backlog."""

    def test_project_not_found(self, client):
        with patch(_GET_PROJECT, return_value=None):
            resp = client.get("/projects/nonexistent/backlog")
        assert resp.status_code == 404

    def test_empty_backlog(self, client):
        with (
            patch(_GET_PROJECT, return_value={"project_id": "p1"}),
            patch(f"{_PKG}.get_db", return_value=_mock_db([])),
        ):
            resp = client.get("/projects/p1/backlog")
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_id"] == "p1"
        assert body["count"] == 0
        assert body["items"] == []

    def test_idea_with_sections(self, client):
        docs = [
            {
                "run_id": "run1",
                "project_id": "p1",
                "idea": "Build a feature",
                "status": "inprogress",
                "sections": {
                    "overview": {
                        "title": "Overview",
                        "content": "Some content",
                        "is_approved": True,
                    },
                    "tech": {
                        "title": "Tech Stack",
                        "content": "",
                        "is_approved": False,
                    },
                },
                "created_at": "2026-01-01T00:00:00Z",
            },
        ]
        with (
            patch(_GET_PROJECT, return_value={"project_id": "p1"}),
            patch(f"{_PKG}.get_db", return_value=_mock_db(docs)),
        ):
            resp = client.get("/projects/p1/backlog")
        assert resp.status_code == 200
        body = resp.json()
        # 1 idea + 2 sections = 3 items
        assert body["count"] == 3

        idea_items = [i for i in body["items"] if i["kind"] == "idea"]
        assert len(idea_items) == 1
        assert idea_items[0]["id"] == "idea:run1"

        section_items = [i for i in body["items"] if i["kind"] == "prd_section"]
        assert len(section_items) == 2

        # First section blocked only by idea
        overview = next(s for s in section_items if s["section_key"] == "overview")
        assert "idea:run1" in overview["blocked_by"]
        assert overview["status"] == "approved"

        # Second section blocked by idea + previous section
        tech = next(s for s in section_items if s["section_key"] == "tech")
        assert "idea:run1" in tech["blocked_by"]
        assert f"section:run1:overview" in tech["blocked_by"]
        assert tech["status"] == "pending"  # no content

    def test_completed_with_publishing(self, client):
        docs = [
            {
                "run_id": "run2",
                "project_id": "p1",
                "idea": "Done feature",
                "status": "completed",
                "sections": {
                    "overview": {
                        "title": "Overview",
                        "content": "Done",
                        "is_approved": True,
                    },
                },
                "created_at": "2026-01-01T00:00:00Z",
                "completed_at": "2026-01-02T00:00:00Z",
                # No confluence_url or jira_output
            },
        ]
        with (
            patch(_GET_PROJECT, return_value={"project_id": "p1"}),
            patch(f"{_PKG}.get_db", return_value=_mock_db(docs)),
        ):
            resp = client.get("/projects/p1/backlog")
        assert resp.status_code == 200
        body = resp.json()
        # 1 idea + 1 section + 2 publishing = 4
        assert body["count"] == 4
        pub_items = [i for i in body["items"] if i["kind"].startswith("publish_")]
        assert len(pub_items) == 2
        kinds = {i["kind"] for i in pub_items}
        assert "publish_confluence" in kinds
        assert "publish_jira" in kinds

        # Publishing items should be blocked by sections
        for pi in pub_items:
            assert "section:run2:overview" in pi["blocked_by"]

    def test_already_published_excluded(self, client):
        docs = [
            {
                "run_id": "run3",
                "project_id": "p1",
                "idea": "Published feature",
                "status": "completed",
                "sections": {
                    "overview": {
                        "title": "Overview",
                        "content": "Done",
                        "is_approved": True,
                    },
                },
                "confluence_url": "https://example.com/123",
                "jira_output": "PROJ-1",
                "created_at": "2026-01-01T00:00:00Z",
            },
        ]
        with (
            patch(_GET_PROJECT, return_value={"project_id": "p1"}),
            patch(f"{_PKG}.get_db", return_value=_mock_db(docs)),
        ):
            resp = client.get("/projects/p1/backlog")
        assert resp.status_code == 200
        body = resp.json()
        pub_items = [i for i in body["items"] if i["kind"].startswith("publish_")]
        assert len(pub_items) == 0
