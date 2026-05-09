"""Tests for the Code Repos API router."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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


class TestListCodeRepos:
    @patch("crewai_productfeature_planner.apis.code_repos.router.list_code_repos")
    def test_list_empty(self, mock_list, client):
        mock_list.return_value = []
        resp = client.get(
            "/projects/p1/repos",
            
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"items": [], "total": 0}

    @patch("crewai_productfeature_planner.apis.code_repos.router.list_code_repos")
    def test_list_with_repos(self, mock_list, client):
        mock_list.return_value = [
            {
                "repo_id": "r1",
                "project_id": "p1",
                "url": "https://github.com/org/repo",
                "name": "repo",
                "owner": "org",
                "status": "ready",
                "analysis": {
                    "architecture_summary": "Monorepo",
                    "primary_language": "Python",
                    "frameworks": ["FastAPI"],
                    "dependencies_count": 42,
                    "api_surface_count": 10,
                    "schema_entities_count": 5,
                },
                "kb_path": "/hub/repo",
                "last_analyzed_at": "2026-05-01T00:00:00Z",
                "created_at": "2026-04-01T00:00:00Z",
            }
        ]
        resp = client.get("/projects/p1/repos")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["repo_id"] == "r1"
        assert item["architecture_summary"] == "Monorepo"
        assert item["primary_language"] == "Python"
        assert item["frameworks"] == ["FastAPI"]
        assert item["kb_hub_link"] == "/hub/repo"
        assert item["last_analyzed"] == "2026-05-01T00:00:00Z"


class TestGetCodeRepo:
    @patch("crewai_productfeature_planner.apis.code_repos.router.get_code_repo")
    def test_not_found(self, mock_get, client):
        mock_get.return_value = None
        resp = client.get(
            "/projects/p1/repos/r1",
            
        )
        assert resp.status_code == 404


class TestRegisterRepo:
    @patch("crewai_productfeature_planner.apis.code_repos.router.analyze_repo_async")
    @patch("crewai_productfeature_planner.apis.code_repos.router.create_code_repo")
    @patch("crewai_productfeature_planner.apis.code_repos.router.get_project")
    def test_register_success(self, mock_proj, mock_create, mock_analyze, client):
        mock_proj.return_value = {"project_id": "p1", "name": "My Project"}
        mock_create.return_value = {
            "repo_id": "r1",
            "project_id": "p1",
            "url": "https://github.com/org/repo",
            "name": "repo",
            "owner": "org",
            "status": "pending",
            "analysis": None,
            "kb_path": None,
            "last_analyzed_at": None,
            "created_at": "2026-05-01T00:00:00Z",
        }
        resp = client.post(
            "/projects/p1/repos",
            json={"url": "https://github.com/org/repo"},
            
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["repo_id"] == "r1"
        assert data["status"] == "pending"
        assert data["name"] == "repo"
        assert data["frameworks"] == []
        mock_analyze.assert_called_once()

    @patch("crewai_productfeature_planner.apis.code_repos.router.get_project")
    def test_register_invalid_url(self, mock_proj, client):
        mock_proj.return_value = {"project_id": "p1", "name": "My Project"}
        resp = client.post(
            "/projects/p1/repos",
            json={"url": "not-a-github-url"},
            
        )
        assert resp.status_code == 400


class TestDeleteRepo:
    @patch("crewai_productfeature_planner.apis.code_repos.router.delete_code_repo")
    def test_delete_success(self, mock_del, client):
        mock_del.return_value = True
        resp = client.delete(
            "/projects/p1/repos/r1",
            
        )
        assert resp.status_code == 204

    @patch("crewai_productfeature_planner.apis.code_repos.router.delete_code_repo")
    def test_delete_not_found(self, mock_del, client):
        mock_del.return_value = False
        resp = client.delete(
            "/projects/p1/repos/r1",
            
        )
        assert resp.status_code == 404


class TestGithubConnect:
    @patch("crewai_productfeature_planner.apis.code_repos.router.build_oauth_url")
    @patch("crewai_productfeature_planner.apis.code_repos.router.get_project")
    def test_connect_returns_url(self, mock_proj, mock_oauth, client):
        mock_proj.return_value = {"project_id": "p1", "name": "Test"}
        mock_oauth.return_value = "https://github.com/login/oauth/authorize?client_id=test"
        resp = client.post(
            "/projects/p1/github/connect",
            
        )
        assert resp.status_code == 200
        assert "auth_url" in resp.json()

    @patch("crewai_productfeature_planner.apis.code_repos.router.build_oauth_url")
    @patch("crewai_productfeature_planner.apis.code_repos.router.get_project")
    def test_connect_not_configured(self, mock_proj, mock_oauth, client):
        mock_proj.return_value = {"project_id": "p1", "name": "Test"}
        mock_oauth.return_value = None
        resp = client.post(
            "/projects/p1/github/connect",
            
        )
        assert resp.status_code == 503


class TestReanalyzeRepo:
    @patch("crewai_productfeature_planner.apis.code_repos.router.analyze_repo_async")
    @patch("crewai_productfeature_planner.apis.code_repos.router.get_project")
    @patch("crewai_productfeature_planner.apis.code_repos.router.get_code_repo")
    def test_reanalyze(self, mock_repo, mock_proj, mock_analyze, client):
        mock_repo.return_value = {
            "repo_id": "r1",
            "project_id": "p1",
            "url": "https://github.com/org/repo",
            "name": "repo",
            "owner": "org",
            "status": "ready",
            "analysis": None,
            "kb_path": None,
            "last_analyzed_at": None,
            "created_at": "2026-05-01T00:00:00Z",
        }
        mock_proj.return_value = {"project_id": "p1", "name": "Test"}
        resp = client.post(
            "/projects/p1/repos/r1/analyze",
            
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "analyzing"
        assert data["repo_id"] == "r1"
        assert data["name"] == "repo"
        mock_analyze.assert_called_once()
