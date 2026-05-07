"""Tests for the Knowledge API router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app
from crewai_productfeature_planner.apis.sso_auth import require_sso_user


def _test_user():
    return {
        "user_id": "u1",
        "email": "test@example.com",
        "enterprise_id": "ent1",
        "organization_id": "org1",
        "roles": ["user"],
    }


@pytest.fixture
def client():
    app.dependency_overrides[require_sso_user] = lambda: _test_user()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestListKnowledgeDocs:
    @patch("crewai_productfeature_planner.apis.knowledge.router.list_knowledge_documents")
    def test_list_returns_empty(self, mock_list, client):
        mock_list.return_value = []
        resp = client.get(
            "/projects/p1/knowledge",
            
        )
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("crewai_productfeature_planner.apis.knowledge.router.list_knowledge_documents")
    def test_list_returns_docs(self, mock_list, client):
        mock_list.return_value = [
            {
                "doc_id": "d1",
                "project_id": "p1",
                "source_type": "upload",
                "filename": "test.pdf",
                "url": None,
                "file_size": 1000,
                "content_type": "application/pdf",
                "status": "reviewed",
                "included": True,
                "review": {"summary": "A doc"},
                "created_by": "u1",
                "created_at": "2026-01-01T00:00:00",
                "updated_at": "2026-01-01T00:00:00",
            }
        ]
        resp = client.get(
            "/projects/p1/knowledge",
            
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["doc_id"] == "d1"


class TestGetKnowledgeDoc:
    @patch("crewai_productfeature_planner.apis.knowledge.router.get_knowledge_document")
    def test_get_not_found(self, mock_get, client):
        mock_get.return_value = None
        resp = client.get(
            "/projects/p1/knowledge/d1",
            
        )
        assert resp.status_code == 404

    @patch("crewai_productfeature_planner.apis.knowledge.router.get_knowledge_document")
    def test_get_found(self, mock_get, client):
        mock_get.return_value = {
            "doc_id": "d1",
            "project_id": "p1",
            "source_type": "url",
            "filename": None,
            "url": "https://example.com",
            "file_size": None,
            "content_type": "text/html",
            "status": "reviewed",
            "included": True,
            "review": None,
            "created_by": "u1",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
        resp = client.get(
            "/projects/p1/knowledge/d1",
            
        )
        assert resp.status_code == 200
        assert resp.json()["doc_id"] == "d1"


class TestPatchKnowledgeDoc:
    @patch("crewai_productfeature_planner.apis.knowledge.router.toggle_included")
    def test_toggle_success(self, mock_toggle, client):
        mock_toggle.return_value = True
        resp = client.patch(
            "/projects/p1/knowledge/d1",
            json={"included": False},
            
        )
        assert resp.status_code == 200
        assert resp.json()["included"] is False

    @patch("crewai_productfeature_planner.apis.knowledge.router.toggle_included")
    def test_toggle_not_found(self, mock_toggle, client):
        mock_toggle.return_value = False
        resp = client.patch(
            "/projects/p1/knowledge/d1",
            json={"included": True},
            
        )
        assert resp.status_code == 404


class TestDeleteKnowledgeDoc:
    @patch("crewai_productfeature_planner.apis.knowledge.router.knowledge_storage")
    @patch("crewai_productfeature_planner.apis.knowledge.router.delete_knowledge_document")
    @patch("crewai_productfeature_planner.apis.knowledge.router.get_knowledge_document")
    def test_delete_success(self, mock_get, mock_del, mock_storage, client):
        mock_get.return_value = {"doc_id": "d1", "gcs_path": "projects/p1/d1/file.pdf"}
        mock_del.return_value = True
        mock_storage.delete_file.return_value = True
        resp = client.delete(
            "/projects/p1/knowledge/d1",
            
        )
        assert resp.status_code == 204

    @patch("crewai_productfeature_planner.apis.knowledge.router.get_knowledge_document")
    def test_delete_not_found(self, mock_get, client):
        mock_get.return_value = None
        resp = client.delete(
            "/projects/p1/knowledge/d1",
            
        )
        assert resp.status_code == 404


class TestGetSummary:
    @patch("crewai_productfeature_planner.apis.knowledge.router.get_knowledge_summary")
    def test_get_summary_empty(self, mock_get, client):
        mock_get.return_value = None
        resp = client.get(
            "/projects/p1/knowledge/summary",
            
        )
        assert resp.status_code == 200
        assert resp.json()["project_id"] == "p1"
        assert resp.json()["unified_summary"] == ""

    @patch("crewai_productfeature_planner.apis.knowledge.router.get_knowledge_summary")
    def test_get_summary_exists(self, mock_get, client):
        mock_get.return_value = {
            "project_id": "p1",
            "unified_summary": "Summary text",
            "unified_bullets": ["a", "b"],
            "contradictions": [{"claim_a": "X", "source_a": "doc1", "claim_b": "Y", "source_b": "doc2", "severity": "high"}],
            "doc_count": 2,
            "generated_at": "2026-01-01T00:00:00",
        }
        resp = client.get(
            "/projects/p1/knowledge/summary",
            
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["unified_summary"] == "Summary text"
        assert len(data["contradictions"]) == 1
