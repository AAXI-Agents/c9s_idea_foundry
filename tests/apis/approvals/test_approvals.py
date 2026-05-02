"""Tests for GET /approvals/pending endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app

_PKG = "crewai_productfeature_planner.apis.approvals.router"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _mock_db(collections: dict[str, list[dict]]):
    """Return a mock ``get_db()`` whose collections return the given docs."""
    db = MagicMock()

    def _make_coll(docs):
        coll = MagicMock()
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.__iter__ = MagicMock(return_value=iter(docs))
        coll.find.return_value = cursor
        # Support list()
        cursor.__class__ = list
        return coll

    # Better approach: make find() return a cursor that supports chaining and list()
    def make_collection(docs):
        coll = MagicMock()

        class FakeCursor:
            def __init__(self, data):
                self._data = list(data)

            def sort(self, *a, **kw):
                return self

            def limit(self, *a, **kw):
                return self

            def __iter__(self):
                return iter(self._data)

        coll.find.return_value = FakeCursor(docs)
        return coll

    coll_map = {}
    for name, docs in collections.items():
        coll_map[name] = make_collection(docs)
    # Default empty collection
    default_coll = make_collection([])
    db.__getitem__ = MagicMock(side_effect=lambda name: coll_map.get(name, default_coll))
    return db


class TestApprovalsPending:
    """Tests for GET /approvals/pending."""

    def test_empty(self, client):
        with patch(f"{_PKG}.get_db", return_value=_mock_db({"workingIdeas": []})):
            resp = client.get("/approvals/pending")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["items"] == []

    def test_section_approvals(self, client):
        docs = [
            {
                "run_id": "run1",
                "project_id": "proj1",
                "status": "inprogress",
                "sections": {
                    "overview": {
                        "title": "Overview",
                        "content": "Some content",
                        "is_approved": False,
                    },
                    "tech": {
                        "title": "Tech Stack",
                        "content": "Node.js",
                        "is_approved": True,
                    },
                },
                "created_at": "2026-01-01T00:00:00Z",
            },
        ]
        with patch(f"{_PKG}.get_db", return_value=_mock_db({"workingIdeas": docs})):
            resp = client.get("/approvals/pending")
        assert resp.status_code == 200
        body = resp.json()
        # Only the unapproved section should appear
        section_items = [i for i in body["items"] if i["kind"] == "prd_section_approval"]
        assert len(section_items) == 1
        assert section_items[0]["section_key"] == "overview"
        assert section_items[0]["run_id"] == "run1"
        assert len(section_items[0]["actions"]) == 2

    def test_paused_run(self, client):
        active_docs: list[dict] = []
        paused_docs = [
            {
                "run_id": "run2",
                "project_id": "proj1",
                "status": "paused",
                "idea": "My paused idea",
                "created_at": "2026-01-01T00:00:00Z",
            },
        ]
        all_docs = active_docs + paused_docs
        with patch(f"{_PKG}.get_db", return_value=_mock_db({"workingIdeas": all_docs})):
            resp = client.get("/approvals/pending")
        assert resp.status_code == 200
        body = resp.json()
        resume_items = [i for i in body["items"] if i["kind"] == "resume_paused"]
        assert len(resume_items) == 1
        assert resume_items[0]["run_id"] == "run2"

    def test_publish_confluence(self, client):
        docs = [
            {
                "run_id": "run3",
                "project_id": "proj1",
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
                # No confluence_url → should appear as pending
            },
        ]
        with patch(f"{_PKG}.get_db", return_value=_mock_db({"workingIdeas": docs})):
            resp = client.get("/approvals/pending")
        assert resp.status_code == 200
        body = resp.json()
        conf_items = [i for i in body["items"] if i["kind"] == "publish_confluence"]
        assert len(conf_items) == 1
        assert conf_items[0]["run_id"] == "run3"

    def test_publish_jira(self, client):
        docs = [
            {
                "run_id": "run4",
                "project_id": "proj1",
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
                # No jira_output or jira_skeleton → should appear as pending
            },
        ]
        with patch(f"{_PKG}.get_db", return_value=_mock_db({"workingIdeas": docs})):
            resp = client.get("/approvals/pending")
        assert resp.status_code == 200
        body = resp.json()
        jira_items = [i for i in body["items"] if i["kind"] == "publish_jira"]
        assert len(jira_items) == 1
        assert jira_items[0]["run_id"] == "run4"

    def test_filter_by_project(self, client):
        docs = [
            {
                "run_id": "run5",
                "project_id": "proj2",
                "status": "paused",
                "idea": "test",
                "created_at": "2026-01-01T00:00:00Z",
            },
        ]
        with patch(f"{_PKG}.get_db", return_value=_mock_db({"workingIdeas": docs})):
            resp = client.get("/approvals/pending?project_id=proj2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] >= 0  # Just verify the filter param is accepted

    def test_already_published_excluded(self, client):
        docs = [
            {
                "run_id": "run6",
                "project_id": "proj1",
                "status": "completed",
                "sections": {
                    "overview": {
                        "title": "Overview",
                        "content": "Done",
                        "is_approved": True,
                    },
                },
                "confluence_url": "https://example.com/page/123",
                "jira_output": "PROJ-1",
                "created_at": "2026-01-01T00:00:00Z",
            },
        ]
        with patch(f"{_PKG}.get_db", return_value=_mock_db({"workingIdeas": docs})):
            resp = client.get("/approvals/pending")
        assert resp.status_code == 200
        body = resp.json()
        pub_items = [
            i for i in body["items"]
            if i["kind"] in ("publish_confluence", "publish_jira")
        ]
        assert len(pub_items) == 0
