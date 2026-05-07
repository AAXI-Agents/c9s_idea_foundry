"""Tests for the knowledge_summaries MongoDB repository."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.knowledge_summaries.repository import (
    KNOWLEDGE_SUMMARIES_COLLECTION,
    delete_knowledge_summary,
    get_knowledge_summary,
    upsert_knowledge_summary,
)


@pytest.fixture
def tenant():
    return TenantContext(enterprise_id="ent1", organization_id="org1")


@pytest.fixture
def mock_col():
    with patch(
        "crewai_productfeature_planner.mongodb.knowledge_summaries.repository._col"
    ) as m:
        col = MagicMock()
        m.return_value = col
        yield col


class TestUpsertKnowledgeSummary:
    def test_upserts(self, mock_col, tenant):
        mock_col.replace_one.return_value = MagicMock()
        result = upsert_knowledge_summary(
            project_id="p1",
            unified_summary="A summary.",
            unified_bullets=["bullet1"],
            contradictions=[],
            doc_count=3,
            tenant=tenant,
        )
        assert result is not None
        assert result["unified_summary"] == "A summary."
        assert result["doc_count"] == 3
        mock_col.replace_one.assert_called_once()


class TestGetKnowledgeSummary:
    def test_returns_summary(self, mock_col, tenant):
        mock_col.find_one.return_value = {
            "_id": "x",
            "project_id": "p1",
            "unified_summary": "test",
        }
        result = get_knowledge_summary(project_id="p1", tenant=tenant)
        assert result == {"project_id": "p1", "unified_summary": "test"}

    def test_returns_none_when_not_found(self, mock_col, tenant):
        mock_col.find_one.return_value = None
        result = get_knowledge_summary(project_id="p1", tenant=tenant)
        assert result is None


class TestDeleteKnowledgeSummary:
    def test_deletes(self, mock_col, tenant):
        mock_col.delete_one.return_value = MagicMock(deleted_count=1)
        assert delete_knowledge_summary(project_id="p1", tenant=tenant) is True

    def test_returns_false_when_not_found(self, mock_col, tenant):
        mock_col.delete_one.return_value = MagicMock(deleted_count=0)
        assert delete_knowledge_summary(project_id="p1", tenant=tenant) is False
