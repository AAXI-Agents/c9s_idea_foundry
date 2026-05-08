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
    @patch("crewai_productfeature_planner.apis.knowledge.router.count_knowledge_documents")
    @patch("crewai_productfeature_planner.apis.knowledge.router.get_knowledge_summary")
    def test_get_summary_empty(self, mock_get, mock_count, client):
        mock_get.return_value = None
        mock_count.return_value = 3
        resp = client.get(
            "/projects/p1/knowledge/summary",
            
        )
        assert resp.status_code == 200
        assert resp.json()["project_id"] == "p1"
        assert resp.json()["unified_summary"] == ""
        assert resp.json()["doc_count"] == 3

    @patch("crewai_productfeature_planner.apis.knowledge.router.count_knowledge_documents")
    @patch("crewai_productfeature_planner.apis.knowledge.router.get_knowledge_summary")
    def test_get_summary_exists(self, mock_get, mock_count, client):
        mock_get.return_value = {
            "project_id": "p1",
            "unified_summary": "Summary text",
            "unified_bullets": ["a", "b"],
            "contradictions": [{"claim_a": "X", "source_a": "doc1", "claim_b": "Y", "source_b": "doc2", "severity": "high"}],
            "doc_count": 2,
            "generated_at": "2026-01-01T00:00:00",
        }
        mock_count.return_value = 5
        resp = client.get(
            "/projects/p1/knowledge/summary",
            
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["unified_summary"] == "Summary text"
        assert data["doc_count"] == 5
        assert len(data["contradictions"]) == 1


class TestRegenerateSummary:
    @patch("crewai_productfeature_planner.apis.knowledge.router.count_knowledge_documents")
    @patch("crewai_productfeature_planner.apis.knowledge.router.get_knowledge_summary")
    @patch("crewai_productfeature_planner.apis.knowledge.router.aggregate_knowledge")
    def test_regenerate_returns_fresh_summary(self, mock_agg, mock_get, mock_count, client):
        mock_agg.return_value = None
        mock_get.return_value = {
            "project_id": "p1",
            "unified_summary": "Regenerated",
            "unified_bullets": ["x"],
            "contradictions": [],
            "doc_count": 0,
            "generated_at": "2026-05-07T00:00:00",
        }
        mock_count.return_value = 4
        resp = client.post("/projects/p1/knowledge/summary/regenerate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unified_summary"] == "Regenerated"
        assert data["doc_count"] == 4
        mock_agg.assert_called_once()

    @patch("crewai_productfeature_planner.apis.knowledge.router.count_knowledge_documents")
    @patch("crewai_productfeature_planner.apis.knowledge.router.get_knowledge_summary")
    @patch("crewai_productfeature_planner.apis.knowledge.router.aggregate_knowledge")
    def test_regenerate_no_summary_returns_doc_count(self, mock_agg, mock_get, mock_count, client):
        mock_agg.return_value = None
        mock_get.return_value = None
        mock_count.return_value = 2
        resp = client.post("/projects/p1/knowledge/summary/regenerate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["doc_count"] == 2
        assert data["unified_summary"] == ""


class TestUrlIngestDedup:
    @patch("crewai_productfeature_planner.apis.knowledge.router.find_duplicate_url")
    def test_duplicate_url_returns_409(self, mock_find, client):
        mock_find.return_value = {"doc_id": "existing123"}
        resp = client.post(
            "/projects/p1/knowledge/url",
            json={"url": "https://example.com/doc"},
        )
        assert resp.status_code == 409
        assert "already ingested" in resp.json()["detail"].lower()
        assert resp.headers.get("X-Existing-Doc-Id") == "existing123"

    @patch("crewai_productfeature_planner.apis.knowledge.router.review_document_async")
    @patch("crewai_productfeature_planner.apis.knowledge.router.update_knowledge_document")
    @patch("crewai_productfeature_planner.apis.knowledge.router.create_knowledge_document")
    @patch("crewai_productfeature_planner.apis.knowledge.router.find_duplicate_url")
    def test_non_duplicate_url_proceeds(self, mock_find, mock_create, mock_update, mock_review, client):
        mock_find.return_value = None
        mock_create.return_value = {"doc_id": "new1"}
        resp = client.post(
            "/projects/p1/knowledge/url",
            json={"url": "https://example.com/new"},
        )
        # Will fail at HTTP fetch in test env, but dedup passed
        # The test verifies the dedup check didn't block
        mock_find.assert_called_once()


class TestRetriggerReview:
    """Tests for POST /{doc_id}/review (retrigger Content Reviewer)."""

    @patch("crewai_productfeature_planner.apis.knowledge.router.get_knowledge_document")
    def test_review_doc_not_found(self, mock_get, client):
        mock_get.return_value = None
        resp = client.post("/projects/p1/knowledge/d1/review")
        assert resp.status_code == 404

    @patch("crewai_productfeature_planner.apis.knowledge.router.review_document_async")
    @patch("crewai_productfeature_planner.apis.knowledge.router.extract_text", return_value="Hello world content")
    @patch("crewai_productfeature_planner.apis.knowledge.router.knowledge_storage")
    @patch("crewai_productfeature_planner.apis.knowledge.router.get_knowledge_document")
    def test_review_review_failed_with_gcs(self, mock_get, mock_storage, mock_extract, mock_review, client):
        """review_failed doc with GCS content triggers review."""
        mock_get.return_value = {
            "doc_id": "d1",
            "project_id": "p1",
            "status": "review_failed",
            "gcs_path": "projects/p1/d1/file.txt",
            "filename": "file.txt",
            "content_type": "text/plain",
        }
        mock_storage.download_as_bytes.return_value = b"Hello world content"
        resp = client.post("/projects/p1/knowledge/d1/review")
        assert resp.status_code == 200
        assert resp.json()["status"] == "reviewing"
        mock_review.assert_called_once()

    @patch("crewai_productfeature_planner.apis.knowledge.router.review_document_async")
    @patch("crewai_productfeature_planner.apis.knowledge.router.extract_text", return_value="Some content")
    @patch("crewai_productfeature_planner.apis.knowledge.router.knowledge_storage")
    @patch("crewai_productfeature_planner.apis.knowledge.router.get_knowledge_document")
    def test_review_reviewed_doc_succeeds(self, mock_get, mock_storage, mock_extract, mock_review, client):
        """Already-reviewed doc can be re-reviewed."""
        mock_get.return_value = {
            "doc_id": "d1",
            "project_id": "p1",
            "status": "reviewed",
            "gcs_path": "projects/p1/d1/file.txt",
            "filename": "file.txt",
            "content_type": "text/plain",
        }
        mock_storage.download_as_bytes.return_value = b"Some content"
        resp = client.post("/projects/p1/knowledge/d1/review")
        assert resp.status_code == 200
        assert resp.json()["status"] == "reviewing"

    @patch("crewai_productfeature_planner.apis.knowledge.router.get_knowledge_document")
    def test_review_uploading_returns_409(self, mock_get, client):
        """Doc with status 'uploading' cannot be reviewed."""
        mock_get.return_value = {
            "doc_id": "d1",
            "project_id": "p1",
            "status": "uploading",
        }
        resp = client.post("/projects/p1/knowledge/d1/review")
        assert resp.status_code == 409

    @patch("crewai_productfeature_planner.apis.knowledge.router.get_knowledge_document")
    def test_review_upload_failed_returns_409(self, mock_get, client):
        """Doc with status 'upload_failed' cannot be reviewed."""
        mock_get.return_value = {
            "doc_id": "d1",
            "project_id": "p1",
            "status": "upload_failed",
        }
        resp = client.post("/projects/p1/knowledge/d1/review")
        assert resp.status_code == 409

    @patch("crewai_productfeature_planner.apis.knowledge.router.get_knowledge_document")
    def test_review_fetching_returns_409(self, mock_get, client):
        """Doc with status 'fetching' cannot be reviewed."""
        mock_get.return_value = {
            "doc_id": "d1",
            "project_id": "p1",
            "status": "fetching",
        }
        resp = client.post("/projects/p1/knowledge/d1/review")
        assert resp.status_code == 409

    @patch("crewai_productfeature_planner.apis.knowledge.router.extract_text", return_value=None)
    @patch("crewai_productfeature_planner.apis.knowledge.router.knowledge_storage")
    @patch("crewai_productfeature_planner.apis.knowledge.router.get_knowledge_document")
    def test_review_no_content_returns_422(self, mock_get, mock_storage, mock_extract, client):
        """Doc exists with reviewable status but no content available."""
        mock_get.return_value = {
            "doc_id": "d1",
            "project_id": "p1",
            "status": "review_failed",
            "gcs_path": "projects/p1/d1/file.txt",
            "filename": "file.txt",
            "content_type": "text/plain",
        }
        mock_storage.download_as_bytes.return_value = b"something"
        resp = client.post("/projects/p1/knowledge/d1/review")
        assert resp.status_code == 422
