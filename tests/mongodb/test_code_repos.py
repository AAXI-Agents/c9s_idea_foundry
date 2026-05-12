"""Tests for the code_repos MongoDB repository."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.code_repos.repository import (
    CODE_REPOS_COLLECTION,
    count_code_repos,
    create_code_repo,
    delete_code_repo,
    get_code_repo,
    list_code_repos,
    set_analysis_result,
)


@pytest.fixture
def tenant():
    return TenantContext(enterprise_id="ent1", organization_id="org1")


@pytest.fixture
def mock_col():
    with patch(
        "crewai_productfeature_planner.mongodb.code_repos.repository._col"
    ) as m:
        col = MagicMock()
        m.return_value = col
        yield col


class TestCreateCodeRepo:
    def test_creates_repo(self, mock_col, tenant):
        mock_col.insert_one.return_value = MagicMock()
        result = create_code_repo(
            project_id="p1",
            url="https://github.com/org/repo",
            name="repo",
            owner="org",
            created_by="user1",
            tenant=tenant,
        )
        assert result is not None
        assert result["name"] == "repo"
        assert result["owner"] == "org"
        assert result["status"] == "pending"
        assert result["enterprise_id"] == "ent1"

    def test_returns_none_on_error(self, mock_col, tenant):
        from pymongo.errors import PyMongoError

        mock_col.insert_one.side_effect = PyMongoError("fail")
        result = create_code_repo(
            project_id="p1",
            url="https://github.com/org/repo",
            name="repo",
            owner="org",
            created_by="user1",
            tenant=tenant,
        )
        assert result is None


class TestGetCodeRepo:
    def test_returns_repo(self, mock_col, tenant):
        mock_col.find_one.return_value = {"_id": "x", "repo_id": "r1"}
        result = get_code_repo(repo_id="r1", project_id="p1", tenant=tenant)
        assert result == {"repo_id": "r1"}


class TestListCodeRepos:
    def test_returns_list(self, mock_col, tenant):
        mock_col.find.return_value = MagicMock(
            skip=MagicMock(return_value=MagicMock(
                limit=MagicMock(return_value=[
                    {"_id": "x1", "repo_id": "r1"},
                    {"_id": "x2", "repo_id": "r2"},
                ])
            ))
        )
        result = list_code_repos(project_id="p1", tenant=tenant)
        assert len(result) == 2

    def test_passes_skip_limit(self, mock_col, tenant):
        chain = MagicMock()
        chain.skip.return_value = chain
        chain.limit.return_value = []
        mock_col.find.return_value = chain
        list_code_repos(project_id="p1", tenant=tenant, skip=10, limit=5)
        chain.skip.assert_called_once_with(10)
        chain.limit.assert_called_once_with(5)


class TestCountCodeRepos:
    def test_counts(self, mock_col, tenant):
        mock_col.count_documents.return_value = 3
        assert count_code_repos(project_id="p1", tenant=tenant) == 3

    def test_returns_zero_on_error(self, mock_col, tenant):
        from pymongo.errors import PyMongoError
        mock_col.count_documents.side_effect = PyMongoError("fail")
        assert count_code_repos(project_id="p1", tenant=tenant) == 0


class TestDeleteCodeRepo:
    def test_deletes(self, mock_col, tenant):
        mock_col.delete_one.return_value = MagicMock(deleted_count=1)
        assert delete_code_repo(repo_id="r1", project_id="p1", tenant=tenant) is True


class TestSetAnalysisResult:
    def test_sets_analysis(self, mock_col, tenant):
        mock_col.update_one.return_value = MagicMock(modified_count=1)
        analysis = {"architecture": "monolith", "tech_stack": ["python"]}
        result = set_analysis_result(
            repo_id="r1",
            project_id="p1",
            analysis=analysis,
            kb_path="enterprises/ent/projects/proj/repos/repo/",
            tenant=tenant,
        )
        assert result is True
