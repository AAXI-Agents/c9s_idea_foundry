"""Tests for the webhook management router (config, subscriptions, events)."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app
from crewai_productfeature_planner.apis.admin_deps import require_enterprise_admin
from crewai_productfeature_planner.apis.sso_auth import require_sso_user

_SUBS_REPO = "crewai_productfeature_planner.apis.webhook_management._subscriptions"
_DELIVERIES_REPO = "crewai_productfeature_planner.apis.webhook_management._events"


def _admin_user():
    return {
        "user_id": "admin-001",
        "email": "admin@example.com",
        "roles": ["admin", "enterprise_admin"],
        "enterprise_id": "ent-test",
        "organization_id": "org-001",
    }


def _regular_user():
    return {
        "user_id": "user-002",
        "email": "user@example.com",
        "roles": ["user"],
        "enterprise_id": "ent-test",
        "organization_id": "org-001",
    }


@pytest.fixture()
def admin_client():
    app.dependency_overrides[require_sso_user] = lambda: _admin_user()
    app.dependency_overrides[require_enterprise_admin] = lambda: _admin_user()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def user_client():
    app.dependency_overrides[require_sso_user] = lambda: _regular_user()
    app.dependency_overrides.pop(require_enterprise_admin, None)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── GET /webhook-config ───────────────────────────────────────


class TestWebhookConfig:
    def test_returns_config(self, admin_client):
        with patch(
            "crewai_productfeature_planner.mongodb.integration_credentials.get_credentials",
            return_value={"api_token": "x"},
        ):
            resp = admin_client.get("/webhook-config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "jira" in data
        assert "github" in data
        assert data["jira"]["credential_status"] == "valid"

    def test_regular_user_gets_403(self, user_client):
        resp = user_client.get("/webhook-config")
        assert resp.status_code == 403


# ── GET /webhook-subscriptions ────────────────────────────────


class TestListSubscriptions:
    def test_lists_subscriptions(self, admin_client):
        subs = [
            {"provider": "jira", "enterprise_id": "ent-test", "status": "active"},
            {"provider": "github", "enterprise_id": "ent-test", "status": "active"},
        ]
        with patch(f"{_SUBS_REPO}.list_webhook_subscriptions", return_value=subs):
            resp = admin_client.get("/webhook-subscriptions")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_filter_by_provider(self, admin_client):
        subs = [{"provider": "jira", "enterprise_id": "ent-test", "status": "active"}]
        with patch(f"{_SUBS_REPO}.list_webhook_subscriptions", return_value=subs) as mock:
            resp = admin_client.get("/webhook-subscriptions?provider=jira")
        assert resp.status_code == 200
        mock.assert_called_once_with("ent-test", provider="jira", status_filter=None)


# ── GET /webhook-subscriptions/{key} (Jira) ──────────────────


class TestJiraSubscription:
    def test_get_jira_subscription(self, admin_client):
        sub = {"provider": "jira", "enterprise_id": "ent-test", "status": "active"}
        with patch(f"{_SUBS_REPO}.get_webhook_subscription", return_value=sub):
            resp = admin_client.get("/webhook-subscriptions/PROJ-1")
        assert resp.status_code == 200

    def test_jira_subscription_not_found(self, admin_client):
        with patch(f"{_SUBS_REPO}.get_webhook_subscription", return_value=None):
            resp = admin_client.get("/webhook-subscriptions/NONEXIST")
        assert resp.status_code == 404

    def test_toggle_jira_status(self, admin_client):
        sub = {"provider": "jira", "status": "paused"}
        with patch(f"{_SUBS_REPO}.update_subscription_status", return_value=sub):
            resp = admin_client.patch("/webhook-subscriptions/PROJ-1", json={"status": "paused"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"


# ── POST /webhook-subscriptions/github ────────────────────────


class TestGitHubCreate:
    def test_creates_github_webhook(self, admin_client):
        doc = {"provider": "github", "registered_repos": []}
        with patch(f"{_SUBS_REPO}.add_github_repo", return_value=(doc, "secret123")):
            resp = admin_client.post(
                "/webhook-subscriptions/github",
                json={"project_key": "proj-1", "repo_owner": "org", "repo_name": "repo"},
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["ok"] is True
        assert data["webhook_secret"] == "secret123"

    def test_creates_without_secret_on_existing(self, admin_client):
        doc = {"provider": "github", "registered_repos": []}
        with patch(f"{_SUBS_REPO}.add_github_repo", return_value=(doc, None)):
            resp = admin_client.post(
                "/webhook-subscriptions/github",
                json={"project_key": "proj-2", "repo_owner": "org", "repo_name": "repo2"},
            )
        assert resp.status_code == 201
        assert "webhook_secret" not in resp.json()


# ── GET/PATCH/DELETE /webhook-subscriptions/github/{key} ──────


class TestGitHubManagement:
    def test_get_github_subscription(self, admin_client):
        sub = {"provider": "github", "registered_repos": [{"project_key": "pk"}]}
        with patch(f"{_SUBS_REPO}.get_webhook_subscription", return_value=sub):
            resp = admin_client.get("/webhook-subscriptions/github/pk")
        assert resp.status_code == 200

    def test_toggle_github_status(self, admin_client):
        sub = {"provider": "github", "status": "paused"}
        with patch(f"{_SUBS_REPO}.update_subscription_status", return_value=sub):
            resp = admin_client.patch("/webhook-subscriptions/github/pk", json={"status": "paused"})
        assert resp.status_code == 200

    def test_delete_github_webhook(self, admin_client):
        with patch(f"{_SUBS_REPO}.delete_webhook_subscription", return_value=True):
            resp = admin_client.delete("/webhook-subscriptions/github/pk")
        assert resp.status_code == 204

    def test_delete_not_found(self, admin_client):
        with patch(f"{_SUBS_REPO}.delete_webhook_subscription", return_value=False):
            resp = admin_client.delete("/webhook-subscriptions/github/pk")
        assert resp.status_code == 404

    def test_reveal_secret(self, admin_client):
        with patch(f"{_SUBS_REPO}.reveal_github_secret", return_value="abcd****efgh"):
            resp = admin_client.get("/webhook-subscriptions/github/pk/secret")
        assert resp.status_code == 200
        assert resp.json()["webhook_secret"] == "abcd****efgh"

    def test_regenerate_secret(self, admin_client):
        doc = {"provider": "github", "registered_repos": []}
        with patch(f"{_SUBS_REPO}.regenerate_github_secret", return_value=(doc, "newsecret")):
            resp = admin_client.post("/webhook-subscriptions/github/pk/regenerate-secret")
        assert resp.status_code == 200
        assert resp.json()["webhook_secret"] == "newsecret"


# ── GET /webhook-events ───────────────────────────────────────


class TestWebhookEvents:
    def test_list_events(self, admin_client):
        deliveries = {
            "items": [
                {
                    "delivery_id": "ev-1",
                    "event": "task.completed",
                    "source_service": "c9s_agentic_team",
                    "status": "processed",
                    "received_at": datetime(2026, 5, 13, tzinfo=timezone.utc),
                    "enterprise_id": "ent-test",
                    "issue_key": "PROJ-1",
                    "payload": {"subject": {}},
                    "result": {"dispatched_run_ids": ["run-1"]},
                    "error": None,
                },
            ],
            "total": 1,
            "page": 1,
            "page_size": 50,
        }
        with patch(f"{_DELIVERIES_REPO}.list_deliveries", return_value=deliveries):
            resp = admin_client.get("/webhook-events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["events"][0]["event_id"] == "ev-1"

    def test_get_event_detail(self, admin_client):
        delivery = {
            "delivery_id": "ev-1",
            "event": "task.completed",
            "source_service": "c9s_agentic_team",
            "status": "processed",
            "received_at": "2026-05-13T00:00:00+00:00",
            "enterprise_id": "ent-test",
            "organization_id": "org-001",
            "issue_key": "PROJ-1",
            "payload": {"subject": {}, "headers": {"X-Custom": "val"}},
            "result": {"dispatched_run_ids": ["run-1"]},
            "error": None,
        }
        with patch(f"{_DELIVERIES_REPO}.get_delivery", return_value=delivery):
            resp = admin_client.get("/webhook-events/ev-1")
        assert resp.status_code == 200
        assert resp.json()["event_id"] == "ev-1"

    def test_event_not_found(self, admin_client):
        with patch(f"{_DELIVERIES_REPO}.get_delivery", return_value=None):
            resp = admin_client.get("/webhook-events/ev-nonexist")
        assert resp.status_code == 404

    def test_replay_event(self, admin_client):
        delivery = {
            "delivery_id": "ev-1",
            "event": "task.completed",
            "source_service": "c9s_agentic_team",
            "status": "failed",
            "received_at": "2026-05-13T00:00:00+00:00",
            "enterprise_id": "ent-test",
            "payload": {"event": "task.completed"},
        }
        with patch(f"{_DELIVERIES_REPO}.get_delivery", return_value=delivery):
            resp = admin_client.post("/webhook-events/ev-1/replay")
        assert resp.status_code == 200
        assert "replayed" in resp.json()["message"]

    def test_backfill_events(self, admin_client):
        deliveries = {
            "items": [
                {"delivery_id": "ev-1", "status": "failed", "source_service": "c9s_agentic_team"},
                {"delivery_id": "ev-2", "status": "processed", "source_service": "c9s_agentic_team"},
            ],
            "total": 2,
            "page": 1,
            "page_size": 100,
        }
        with patch(f"{_DELIVERIES_REPO}.list_deliveries", return_value=deliveries):
            resp = admin_client.post(
                "/webhook-events/backfill",
                json={"since": "2026-05-01T00:00:00Z"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enqueued"] == 1
        assert data["skipped"] == 1
