"""Tests for the knowledge_documents MongoDB repository."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.knowledge_documents.repository import (
    KNOWLEDGE_DOCUMENTS_COLLECTION,
    create_knowledge_document,
    delete_knowledge_document,
    get_knowledge_document,
    list_knowledge_documents,
    set_review_result,
    toggle_included,
)


@pytest.fixture
def tenant():
    return TenantContext(enterprise_id="ent1", organization_id="org1")


@pytest.fixture
def mock_col():
    with patch(
        "crewai_productfeature_planner.mongodb.knowledge_documents.repository._col"
    ) as m:
        col = MagicMock()
        m.return_value = col
        yield col


class TestCreateKnowledgeDocument:
    def test_creates_upload_doc(self, mock_col, tenant):
        mock_col.insert_one.return_value = MagicMock()
        result = create_knowledge_document(
            project_id="proj1",
            source_type="upload",
            filename="design.pdf",
            file_size=1024,
            content_type="application/pdf",
            created_by="user1",
            tenant=tenant,
        )
        assert result is not None
        assert result["source_type"] == "upload"
        assert result["filename"] == "design.pdf"
        assert result["status"] == "uploading"
        assert result["included"] is True
        assert result["enterprise_id"] == "ent1"
        assert result["organization_id"] == "org1"
        mock_col.insert_one.assert_called_once()

    def test_creates_url_doc(self, mock_col, tenant):
        mock_col.insert_one.return_value = MagicMock()
        result = create_knowledge_document(
            project_id="proj1",
            source_type="url",
            url="https://example.com/doc",
            created_by="user1",
            tenant=tenant,
        )
        assert result is not None
        assert result["source_type"] == "url"
        assert result["status"] == "fetching"

    def test_returns_none_on_error(self, mock_col, tenant):
        from pymongo.errors import PyMongoError

        mock_col.insert_one.side_effect = PyMongoError("fail")
        result = create_knowledge_document(
            project_id="proj1",
            source_type="upload",
            filename="test.txt",
            created_by="user1",
            tenant=tenant,
        )
        assert result is None


class TestGetKnowledgeDocument:
    def test_returns_doc(self, mock_col, tenant):
        mock_col.find_one.return_value = {"_id": "x", "doc_id": "d1", "project_id": "p1"}
        result = get_knowledge_document(doc_id="d1", project_id="p1", tenant=tenant)
        assert result == {"doc_id": "d1", "project_id": "p1"}

    def test_returns_none_when_not_found(self, mock_col, tenant):
        mock_col.find_one.return_value = None
        result = get_knowledge_document(doc_id="d1", project_id="p1", tenant=tenant)
        assert result is None


class TestListKnowledgeDocuments:
    def test_returns_list(self, mock_col, tenant):
        mock_col.find.return_value = [
            {"_id": "x1", "doc_id": "d1"},
            {"_id": "x2", "doc_id": "d2"},
        ]
        result = list_knowledge_documents(project_id="p1", tenant=tenant)
        assert len(result) == 2
        assert all("_id" not in d for d in result)


class TestToggleIncluded:
    def test_toggles(self, mock_col, tenant):
        mock_col.update_one.return_value = MagicMock(modified_count=1)
        result = toggle_included(
            doc_id="d1", project_id="p1", included=False, tenant=tenant
        )
        assert result is True


class TestDeleteKnowledgeDocument:
    def test_deletes(self, mock_col, tenant):
        mock_col.delete_one.return_value = MagicMock(deleted_count=1)
        result = delete_knowledge_document(doc_id="d1", project_id="p1", tenant=tenant)
        assert result is True

    def test_returns_false_when_not_found(self, mock_col, tenant):
        mock_col.delete_one.return_value = MagicMock(deleted_count=0)
        result = delete_knowledge_document(doc_id="d1", project_id="p1", tenant=tenant)
        assert result is False


class TestSetReviewResult:
    def test_sets_review(self, mock_col, tenant):
        mock_col.update_one.return_value = MagicMock(modified_count=1)
        review = {"summary": "test", "key_bullets": [], "topics": [], "confidence": 0.9}
        result = set_review_result(
            doc_id="d1", project_id="p1", review=review, tenant=tenant
        )
        assert result is True
