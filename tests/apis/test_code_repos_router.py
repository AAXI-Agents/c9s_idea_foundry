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
    @patch("crewai_productfeature_planner.apis.code_repos.router.count_code_repos")
    @patch("crewai_productfeature_planner.apis.code_repos.router.list_code_repos")
    def test_list_empty(self, mock_list, mock_count, client):
        mock_list.return_value = []
        mock_count.return_value = 0
        resp = client.get(
            "/projects/p1/repos",
            
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"items": [], "total": 0}

    @patch("crewai_productfeature_planner.apis.code_repos.router.count_code_repos")
    @patch("crewai_productfeature_planner.apis.code_repos.router.list_code_repos")
    def test_list_with_repos(self, mock_list, mock_count, client):
        mock_list.return_value = [
            {
                "repo_id": "r1",
                "project_id": "p1",
                "url": "https://github.com/org/repo",
                "name": "repo",
                "owner": "org",
                "status": "analyzed",
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
        mock_count.return_value = 1
        resp = client.get("/projects/p1/repos")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["repo_id"] == "r1"
        assert item["status"] == "ready"  # mapped from "analyzed"
        assert item["architecture_summary"] == "Monorepo"
        assert item["primary_language"] == "Python"
        assert item["frameworks"] == ["FastAPI"]
        assert item["kb_hub_link"] == "/hub/repo"
        assert item["last_analyzed"] == "2026-05-01T00:00:00Z"

    @patch("crewai_productfeature_planner.apis.code_repos.router.count_code_repos")
    @patch("crewai_productfeature_planner.apis.code_repos.router.list_code_repos")
    def test_list_passes_pagination_params(self, mock_list, mock_count, client):
        mock_list.return_value = []
        mock_count.return_value = 0
        resp = client.get("/projects/p1/repos?skip=10&limit=5")
        assert resp.status_code == 200
        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args
        assert call_kwargs.kwargs["skip"] == 10
        assert call_kwargs.kwargs["limit"] == 5


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


class TestStatusMapping:
    """Verify _doc_to_response maps internal statuses to frontend values."""

    def test_analyzed_maps_to_ready(self):
        from crewai_productfeature_planner.apis.code_repos.router import _doc_to_response

        doc = {
            "repo_id": "r1", "project_id": "p1", "url": "https://github.com/o/r",
            "name": "r", "status": "analyzed", "analysis": None,
            "kb_path": None, "last_analyzed_at": None, "created_at": "2026-01-01",
        }
        assert _doc_to_response(doc).status == "ready"

    def test_clone_failed_maps_to_failed(self):
        from crewai_productfeature_planner.apis.code_repos.router import _doc_to_response

        doc = {
            "repo_id": "r1", "project_id": "p1", "url": "https://github.com/o/r",
            "name": "r", "status": "clone_failed", "analysis": None,
            "kb_path": None, "last_analyzed_at": None, "created_at": "2026-01-01",
        }
        assert _doc_to_response(doc).status == "failed"

    def test_analysis_failed_maps_to_failed(self):
        from crewai_productfeature_planner.apis.code_repos.router import _doc_to_response

        doc = {
            "repo_id": "r1", "project_id": "p1", "url": "https://github.com/o/r",
            "name": "r", "status": "analysis_failed", "analysis": None,
            "kb_path": None, "last_analyzed_at": None, "created_at": "2026-01-01",
        }
        assert _doc_to_response(doc).status == "failed"

    def test_pending_passes_through(self):
        from crewai_productfeature_planner.apis.code_repos.router import _doc_to_response

        doc = {
            "repo_id": "r1", "project_id": "p1", "url": "https://github.com/o/r",
            "name": "r", "status": "pending", "analysis": None,
            "kb_path": None, "last_analyzed_at": None, "created_at": "2026-01-01",
        }
        assert _doc_to_response(doc).status == "pending"

    def test_analyzing_passes_through(self):
        from crewai_productfeature_planner.apis.code_repos.router import _doc_to_response

        doc = {
            "repo_id": "r1", "project_id": "p1", "url": "https://github.com/o/r",
            "name": "r", "status": "analyzing", "analysis": None,
            "kb_path": None, "last_analyzed_at": None, "created_at": "2026-01-01",
        }
        assert _doc_to_response(doc).status == "analyzing"


class TestGithubCallbackEncryption:
    """Verify GitHub token is encrypted before storage."""

    @patch("crewai_productfeature_planner.mongodb.project_config.update_project")
    @patch("crewai_productfeature_planner.apis.code_repos.router.encrypt_value")
    @patch("crewai_productfeature_planner.apis.code_repos.router.exchange_code_for_token")
    def test_callback_encrypts_token(self, mock_exchange, mock_encrypt, mock_update, client):
        mock_exchange.return_value = {"access_token": "ghp_secret123"}
        mock_encrypt.return_value = "encrypted_blob"

        resp = client.get("/auth/github/callback?code=abc&state=p1")

        assert resp.status_code == 200
        mock_encrypt.assert_called_once_with("ghp_secret123")
        mock_update.assert_called_once()
        updates = mock_update.call_args.kwargs["updates"]
        assert updates["github_token"] == "encrypted_blob"
