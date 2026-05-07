"""Tests for Jira webhook handler (Phase 3)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app

_WEBHOOK = "crewai_productfeature_planner.apis.project_ideas._route_jira_webhook"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestJiraWebhook:
    def test_ignores_unrelated_event(self, client):
        resp = client.post(
            "/webhooks/jira",
            json={"webhookEvent": "jira:issue_deleted", "issue": {}},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_ignores_no_idea_label(self, client):
        resp = client.post(
            "/webhooks/jira",
            json={
                "webhookEvent": "jira:issue_updated",
                "issue": {
                    "key": "PROJ-123",
                    "fields": {
                        "status": {"name": "Done"},
                        "labels": ["unrelated"],
                    },
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"
        assert "No idea label" in resp.json()["reason"]

    def test_ignores_no_feature_label(self, client):
        resp = client.post(
            "/webhooks/jira",
            json={
                "webhookEvent": "jira:issue_updated",
                "issue": {
                    "key": "PROJ-123",
                    "fields": {
                        "status": {"name": "Done"},
                        "labels": ["idea:idea-001"],
                    },
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"
        assert "No feature label" in resp.json()["reason"]

    def test_processes_status_change(self, client):
        idea_doc = {
            "idea_id": "idea-001",
            "features": [
                {"id": "f1", "name": "Auth", "completion_pct": 0.0, "jira_issues": []},
            ],
            "overall_completion": 0.0,
        }
        with (
            patch(f"{_WEBHOOK}.get_idea", return_value=idea_doc),
            patch(f"{_WEBHOOK}.update_features", return_value=True),
            patch(f"{_WEBHOOK}.update_overall_completion", return_value=True),
        ):
            resp = client.post(
                "/webhooks/jira",
                json={
                    "webhookEvent": "jira:issue_updated",
                    "issue": {
                        "key": "PROJ-123",
                        "fields": {
                            "status": {"name": "Done"},
                            "labels": ["idea:idea-001", "feature:f1"],
                        },
                    },
                },
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"
        assert resp.json()["idea_id"] == "idea-001"

    def test_404_idea_not_found(self, client):
        with patch(f"{_WEBHOOK}.get_idea", return_value=None):
            resp = client.post(
                "/webhooks/jira",
                json={
                    "webhookEvent": "jira:issue_updated",
                    "issue": {
                        "key": "PROJ-123",
                        "fields": {
                            "status": {"name": "Done"},
                            "labels": ["idea:missing", "feature:f1"],
                        },
                    },
                },
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_signature_validation_rejects_invalid(self, client, monkeypatch):
        monkeypatch.setenv("JIRA_WEBHOOK_SECRET", "test-secret")
        # Reimport to pick up env var
        import importlib
        import crewai_productfeature_planner.apis.project_ideas._route_jira_webhook as mod
        original = mod._JIRA_WEBHOOK_SECRET
        mod._JIRA_WEBHOOK_SECRET = "test-secret"
        try:
            resp = client.post(
                "/webhooks/jira",
                json={"webhookEvent": "jira:issue_updated", "issue": {}},
                headers={"x-hub-signature": "invalid"},
            )
            assert resp.status_code == 401
        finally:
            mod._JIRA_WEBHOOK_SECRET = original
