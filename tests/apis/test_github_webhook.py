"""Tests for the GitHub push webhook handler."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app
from crewai_productfeature_planner.apis.code_repos import _route_github_webhook


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_debounce():
    """Clear debounce tracker between tests."""
    _route_github_webhook._debounce_tracker.clear()
    yield
    _route_github_webhook._debounce_tracker.clear()


def _make_push_payload(owner="org1", name="repo1", ref="refs/heads/main"):
    return {
        "ref": ref,
        "repository": {
            "full_name": f"{owner}/{name}",
            "default_branch": "main",
        },
        "pusher": {"name": "user1"},
    }


def _sign_payload(payload: bytes, secret: str) -> str:
    sig = hmac.HMAC(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


class TestGithubWebhookSignature:
    @patch.object(_route_github_webhook, "_GITHUB_WEBHOOK_SECRET", "testsecret")
    def test_rejects_missing_signature(self, client):
        resp = client.post(
            "/webhooks/github",
            content=b"{}",
            headers={"x-github-event": "push"},
        )
        assert resp.status_code == 401

    @patch.object(_route_github_webhook, "_GITHUB_WEBHOOK_SECRET", "testsecret")
    def test_rejects_invalid_signature(self, client):
        resp = client.post(
            "/webhooks/github",
            content=b"{}",
            headers={
                "x-github-event": "push",
                "x-hub-signature-256": "sha256=invalid",
            },
        )
        assert resp.status_code == 401

    @patch.object(_route_github_webhook, "_GITHUB_WEBHOOK_SECRET", "")
    def test_accepts_without_secret_configured(self, client):
        """When no secret is configured (dev mode), accept any request."""
        payload = json.dumps(_make_push_payload()).encode()
        with patch(
            "crewai_productfeature_planner.apis.code_repos._route_github_webhook.find_repos_by_github_identity"
        ) as mock_find:
            mock_find.return_value = []
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={"x-github-event": "push"},
            )
        assert resp.status_code == 200

    @patch.object(_route_github_webhook, "_GITHUB_WEBHOOK_SECRET", "mysecret")
    def test_accepts_valid_signature(self, client):
        payload = json.dumps(_make_push_payload()).encode()
        sig = _sign_payload(payload, "mysecret")
        with patch(
            "crewai_productfeature_planner.apis.code_repos._route_github_webhook.find_repos_by_github_identity"
        ) as mock_find:
            mock_find.return_value = []
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "x-github-event": "push",
                    "x-hub-signature-256": sig,
                },
            )
        assert resp.status_code == 200


class TestGithubWebhookEventFiltering:
    def test_ignores_non_push_events(self, client):
        resp = client.post(
            "/webhooks/github",
            content=b"{}",
            headers={"x-github-event": "pull_request"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    @patch(
        "crewai_productfeature_planner.apis.code_repos._route_github_webhook.find_repos_by_github_identity"
    )
    def test_ignores_non_default_branch(self, mock_find, client):
        payload = _make_push_payload(ref="refs/heads/feature-branch")
        resp = client.post(
            "/webhooks/github",
            json=payload,
            headers={"x-github-event": "push"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"
        mock_find.assert_not_called()


class TestGithubWebhookTrigger:
    @patch(
        "crewai_productfeature_planner.apis.code_repos._route_github_webhook.analyze_repo_async"
    )
    @patch(
        "crewai_productfeature_planner.apis.code_repos._route_github_webhook.get_project"
    )
    @patch(
        "crewai_productfeature_planner.apis.code_repos._route_github_webhook.find_repos_by_github_identity"
    )
    def test_triggers_analysis(self, mock_find, mock_proj, mock_analyze, client):
        mock_find.return_value = [
            {
                "repo_id": "r1",
                "project_id": "p1",
                "url": "https://github.com/org1/repo1",
                "name": "repo1",
                "owner": "org1",
            }
        ]
        mock_proj.return_value = {
            "project_id": "p1",
            "name": "My Project",
            "enterprise_id": "ent1",
            "github_token": "tok123",
        }

        payload = _make_push_payload()
        resp = client.post(
            "/webhooks/github",
            json=payload,
            headers={"x-github-event": "push"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "processed"
        assert "r1" in data["triggered"]
        mock_analyze.assert_called_once()
        call_kwargs = mock_analyze.call_args[1]
        assert call_kwargs["repo_id"] == "r1"
        assert call_kwargs["project_id"] == "p1"
        assert call_kwargs["github_token"] == "tok123"

    @patch(
        "crewai_productfeature_planner.apis.code_repos._route_github_webhook.find_repos_by_github_identity"
    )
    def test_no_registered_repos(self, mock_find, client):
        mock_find.return_value = []
        payload = _make_push_payload()
        resp = client.post(
            "/webhooks/github",
            json=payload,
            headers={"x-github-event": "push"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"


class TestGithubWebhookDebounce:
    @patch(
        "crewai_productfeature_planner.apis.code_repos._route_github_webhook.analyze_repo_async"
    )
    @patch(
        "crewai_productfeature_planner.apis.code_repos._route_github_webhook.get_project"
    )
    @patch(
        "crewai_productfeature_planner.apis.code_repos._route_github_webhook.find_repos_by_github_identity"
    )
    def test_debounces_rapid_pushes(self, mock_find, mock_proj, mock_analyze, client):
        mock_find.return_value = [
            {
                "repo_id": "r1",
                "project_id": "p1",
                "url": "https://github.com/org1/repo1",
                "name": "repo1",
                "owner": "org1",
            }
        ]
        mock_proj.return_value = {
            "project_id": "p1",
            "name": "My Project",
            "enterprise_id": "ent1",
        }

        payload = _make_push_payload()

        # First push should trigger
        resp1 = client.post(
            "/webhooks/github",
            json=payload,
            headers={"x-github-event": "push"},
        )
        assert "r1" in resp1.json()["triggered"]

        # Second push should be debounced
        resp2 = client.post(
            "/webhooks/github",
            json=payload,
            headers={"x-github-event": "push"},
        )
        assert "r1" in resp2.json()["debounced"]
        assert mock_analyze.call_count == 1

    @patch(
        "crewai_productfeature_planner.apis.code_repos._route_github_webhook.analyze_repo_async"
    )
    @patch(
        "crewai_productfeature_planner.apis.code_repos._route_github_webhook.get_project"
    )
    @patch(
        "crewai_productfeature_planner.apis.code_repos._route_github_webhook.find_repos_by_github_identity"
    )
    def test_allows_after_debounce_window(self, mock_find, mock_proj, mock_analyze, client):
        mock_find.return_value = [
            {
                "repo_id": "r1",
                "project_id": "p1",
                "url": "https://github.com/org1/repo1",
                "name": "repo1",
                "owner": "org1",
            }
        ]
        mock_proj.return_value = {
            "project_id": "p1",
            "name": "My Project",
            "enterprise_id": "ent1",
        }

        payload = _make_push_payload()

        # First push
        client.post(
            "/webhooks/github",
            json=payload,
            headers={"x-github-event": "push"},
        )

        # Simulate debounce window expiry
        _route_github_webhook._debounce_tracker["r1"] = time.time() - 400

        # Second push should trigger (debounce expired)
        resp = client.post(
            "/webhooks/github",
            json=payload,
            headers={"x-github-event": "push"},
        )
        assert "r1" in resp.json()["triggered"]
        assert mock_analyze.call_count == 2


class TestGithubWebhookMultipleRepos:
    @patch(
        "crewai_productfeature_planner.apis.code_repos._route_github_webhook.analyze_repo_async"
    )
    @patch(
        "crewai_productfeature_planner.apis.code_repos._route_github_webhook.get_project"
    )
    @patch(
        "crewai_productfeature_planner.apis.code_repos._route_github_webhook.find_repos_by_github_identity"
    )
    def test_triggers_all_matching_repos(self, mock_find, mock_proj, mock_analyze, client):
        """Same GitHub repo registered in multiple projects."""
        mock_find.return_value = [
            {
                "repo_id": "r1",
                "project_id": "p1",
                "url": "https://github.com/org1/repo1",
                "name": "repo1",
                "owner": "org1",
            },
            {
                "repo_id": "r2",
                "project_id": "p2",
                "url": "https://github.com/org1/repo1",
                "name": "repo1",
                "owner": "org1",
            },
        ]
        mock_proj.return_value = {
            "project_id": "p1",
            "name": "Project",
            "enterprise_id": "ent1",
        }

        payload = _make_push_payload()
        resp = client.post(
            "/webhooks/github",
            json=payload,
            headers={"x-github-event": "push"},
        )
        data = resp.json()
        assert data["status"] == "processed"
        assert "r1" in data["triggered"]
        assert "r2" in data["triggered"]
        assert mock_analyze.call_count == 2
