"""Tests for the /aw/atlassian/credentials proxy endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


@pytest.fixture(autouse=True, scope="module")
def _mock_crew_jobs():
    with (
        patch("crewai_productfeature_planner.apis.prd._route_actions.create_job"),
        patch(
            "crewai_productfeature_planner.apis.prd._route_actions.find_active_job",
            return_value=None,
        ),
        patch("crewai_productfeature_planner.apis.prd.service.reactivate_job", return_value=True),
        patch("crewai_productfeature_planner.apis.prd.service.create_job"),
        patch("crewai_productfeature_planner.apis.prd.service.update_job_started"),
        patch("crewai_productfeature_planner.apis.prd.service.update_job_completed"),
        patch("crewai_productfeature_planner.apis.prd.service.update_job_status"),
        patch("crewai_productfeature_planner.apis.prd.service.mark_completed"),
        patch(
            "crewai_productfeature_planner.apis.fail_incomplete_jobs_on_startup",
            return_value=0,
        ),
    ):
        yield


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


_CRED_BODY = {
    "jira_base_url": "https://myco.atlassian.net",
    "jira_email": "admin@myco.com",
    "jira_api_token": "secret-token",
    "organization_id": "org-1",
}


# ── POST /aw/atlassian/credentials ──────────────────────────────────


class TestUpsertCredentials:
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.upsert_credentials",
        return_value={"organization_id": "org-1", "provider": "atlassian"},
    )
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.AGENT_WORKER_ENABLED",
        False,
    )
    def test_saves_locally_when_aw_disabled(self, mock_upsert, client):
        resp = client.post("/aw/atlassian/credentials", json=_CRED_BODY)
        assert resp.status_code == 201
        body = resp.json()
        assert body["saved"] is True
        assert body["synced_to_agent_worker"] is False
        assert "Agent Worker not enabled" in body["message"]
        mock_upsert.assert_called_once()

    @patch(
        "crewai_productfeature_planner.mongodb.integration_credentials.mark_synced",
        return_value=True,
    )
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.aw_request",
        new_callable=AsyncMock,
        return_value={"status": "ok"},
    )
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.upsert_credentials",
        return_value={"organization_id": "org-1", "provider": "atlassian"},
    )
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.AGENT_WORKER_ENABLED",
        True,
    )
    def test_saves_and_syncs_when_aw_enabled(self, mock_upsert, mock_aw, mock_sync, client):
        resp = client.post("/aw/atlassian/credentials", json=_CRED_BODY)
        assert resp.status_code == 201
        body = resp.json()
        assert body["saved"] is True
        assert body["synced_to_agent_worker"] is True
        mock_aw.assert_called_once()
        mock_sync.assert_called_once()

    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.upsert_credentials",
        return_value=None,
    )
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.AGENT_WORKER_ENABLED",
        False,
    )
    def test_500_when_local_save_fails(self, mock_upsert, client):
        resp = client.post("/aw/atlassian/credentials", json=_CRED_BODY)
        assert resp.status_code == 500

    def test_validates_required_fields(self, client):
        resp = client.post("/aw/atlassian/credentials", json={"jira_base_url": ""})
        assert resp.status_code == 422

    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.upsert_credentials",
        return_value={"organization_id": "org-1"},
    )
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.AGENT_WORKER_ENABLED",
        True,
    )
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.aw_request",
        new_callable=AsyncMock,
    )
    def test_saves_locally_when_aw_forward_fails(self, mock_aw, mock_upsert, client):
        from crewai_productfeature_planner.apis.agent_worker._client import AgentWorkerError
        mock_aw.side_effect = AgentWorkerError(503, "unreachable")

        resp = client.post("/aw/atlassian/credentials", json=_CRED_BODY)
        assert resp.status_code == 201
        body = resp.json()
        assert body["saved"] is True
        assert body["synced_to_agent_worker"] is False
        assert "sync failed" in body["message"]


# ── POST /aw/atlassian/credentials/{org_id}/test ─────────────────────


class TestTestCredentials:
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.AGENT_WORKER_ENABLED",
        False,
    )
    def test_503_when_aw_disabled(self, client):
        resp = client.post("/aw/atlassian/credentials/org-1/test")
        assert resp.status_code == 503

    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.AGENT_WORKER_ENABLED",
        True,
    )
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.aw_request",
        new_callable=AsyncMock,
        return_value={
            "success": True,
            "message": "All good",
            "jira_valid": True,
            "confluence_valid": True,
        },
    )
    def test_returns_test_result(self, mock_aw, client):
        resp = client.post("/aw/atlassian/credentials/org-1/test")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["jira_valid"] is True

    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.AGENT_WORKER_ENABLED",
        True,
    )
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.aw_request",
        new_callable=AsyncMock,
    )
    def test_handles_aw_error(self, mock_aw, client):
        from crewai_productfeature_planner.apis.agent_worker._client import AgentWorkerError
        mock_aw.side_effect = AgentWorkerError(500, "internal error")

        resp = client.post("/aw/atlassian/credentials/org-1/test")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False


# ── DELETE /aw/atlassian/credentials/{org_id} ────────────────────────


class TestDeleteCredentials:
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.AGENT_WORKER_ENABLED",
        False,
    )
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.delete_credentials",
        return_value=True,
    )
    def test_deletes_locally(self, mock_del, client):
        resp = client.delete("/aw/atlassian/credentials/org-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["local_deleted"] is True
        assert body["agent_worker_deleted"] is False

    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.AGENT_WORKER_ENABLED",
        True,
    )
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.aw_request",
        new_callable=AsyncMock,
        return_value={},
    )
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_credentials.delete_credentials",
        return_value=True,
    )
    def test_deletes_both(self, mock_del, mock_aw, client):
        resp = client.delete("/aw/atlassian/credentials/org-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["local_deleted"] is True
        assert body["agent_worker_deleted"] is True
