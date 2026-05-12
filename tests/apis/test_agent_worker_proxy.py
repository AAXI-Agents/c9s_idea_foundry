"""Tests for the generic /aw/{path} proxy endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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


# ── Proxy disabled ───────────────────────────────────────────


class TestProxyDisabled:
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_proxy.AGENT_WORKER_ENABLED",
        False,
    )
    def test_returns_503_when_disabled(self, client):
        resp = client.get("/aw/flow/slots", headers={"Authorization": "Bearer test-token"})
        assert resp.status_code == 503


# ── Proxy enabled — success ──────────────────────────────────


class TestProxySuccess:
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_proxy.AGENT_WORKER_ENABLED",
        True,
    )
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_proxy.aw_request",
        new_callable=AsyncMock,
        return_value={"status": "ok", "slots": 5},
    )
    def test_get_forwards_and_returns(self, mock_req, client):
        resp = client.get("/aw/flow/slots", headers={"Authorization": "Bearer user-jwt"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        mock_req.assert_awaited_once_with(
            "GET", "/flow/slots", json_body=None, user_token="user-jwt",
        )

    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_proxy.AGENT_WORKER_ENABLED",
        True,
    )
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_proxy.aw_request",
        new_callable=AsyncMock,
        return_value={"created": True},
    )
    def test_post_forwards_json_body(self, mock_req, client):
        resp = client.post(
            "/aw/tasks/PROJ-123/feedback",
            json={"feedback": "looks good"},
            headers={"Authorization": "Bearer user-jwt"},
        )
        assert resp.status_code == 200
        mock_req.assert_awaited_once()
        call_kwargs = mock_req.call_args
        assert call_kwargs.args[0] == "POST"
        assert call_kwargs.args[1] == "/tasks/PROJ-123/feedback"
        assert call_kwargs.kwargs["json_body"] == {"feedback": "looks good"}
        assert call_kwargs.kwargs["user_token"] == "user-jwt"


# ── Proxy error handling ─────────────────────────────────────


class TestProxyErrorHandling:
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_proxy.AGENT_WORKER_ENABLED",
        True,
    )
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_proxy.aw_request",
        new_callable=AsyncMock,
    )
    def test_get_degrades_gracefully_on_503(self, mock_req, client):
        from crewai_productfeature_planner.apis.agent_worker._client import AgentWorkerError

        mock_req.side_effect = AgentWorkerError(503, "unreachable")
        resp = client.get("/aw/readiness", headers={"Authorization": "Bearer user-jwt"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["degraded"] is True

    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_proxy.AGENT_WORKER_ENABLED",
        True,
    )
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_proxy.aw_request",
        new_callable=AsyncMock,
    )
    def test_post_fails_hard_on_503(self, mock_req, client):
        from crewai_productfeature_planner.apis.agent_worker._client import AgentWorkerError

        mock_req.side_effect = AgentWorkerError(503, "unreachable")
        resp = client.post(
            "/aw/flow/pause",
            json={},
            headers={"Authorization": "Bearer user-jwt"},
        )
        assert resp.status_code == 503

    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_proxy.AGENT_WORKER_ENABLED",
        True,
    )
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_proxy.aw_request",
        new_callable=AsyncMock,
    )
    def test_get_propagates_non_transient_errors(self, mock_req, client):
        from crewai_productfeature_planner.apis.agent_worker._client import AgentWorkerError

        mock_req.side_effect = AgentWorkerError(404, "not found")
        resp = client.get("/aw/flow/slots", headers={"Authorization": "Bearer user-jwt"})
        assert resp.status_code == 404

    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_proxy.AGENT_WORKER_ENABLED",
        True,
    )
    @patch(
        "crewai_productfeature_planner.apis.agent_worker._route_proxy.aw_request",
        new_callable=AsyncMock,
    )
    def test_delete_forwards_correctly(self, mock_req, client):
        mock_req.return_value = {}
        resp = client.delete(
            "/aw/settings/org-1",
            headers={"Authorization": "Bearer user-jwt"},
        )
        assert resp.status_code == 200
        mock_req.assert_awaited_once()
        assert mock_req.call_args.args[0] == "DELETE"
