"""Tests for Slack integration endpoints.

POST /integrations/slack/connect
DELETE /integrations/slack
GET /integrations/status (slack field)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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


# ── GET /integrations/status — slack field ───────────────────


class TestIntegrationStatusSlack:
    @patch(
        "crewai_productfeature_planner.apis.integrations.router.get_credentials",
        return_value=None,
    )
    @patch(
        "crewai_productfeature_planner.mongodb.slack_oauth.get_all_teams",
        return_value=[],
    )
    def test_slack_not_configured(self, mock_teams, mock_creds, client):
        resp = client.get("/integrations/status")
        assert resp.status_code == 200
        body = resp.json()
        assert "slack" in body
        assert body["slack"]["configured"] is False

    @patch(
        "crewai_productfeature_planner.apis.integrations.router.get_credentials",
        return_value=None,
    )
    @patch(
        "crewai_productfeature_planner.mongodb.slack_oauth.get_all_teams",
        return_value=[
            {"team_id": "T123", "team_name": "TestWorkspace", "access_token": "xoxb-test"},
        ],
    )
    def test_slack_configured(self, mock_teams, mock_creds, client):
        resp = client.get("/integrations/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["slack"]["configured"] is True
        assert "TestWorkspace" in body["slack"]["base_url"]


# ── POST /integrations/slack/connect ──────────────────────────


class TestSlackConnect:
    @patch(
        "crewai_productfeature_planner.apis.slack.oauth_router.sign_install_state",
        return_value="signed-state-token",
    )
    def test_returns_install_url(self, mock_sign, client, monkeypatch):
        monkeypatch.setenv("SLACK_CLIENT_ID", "123.456")
        monkeypatch.setenv("SLACK_BOT_SCOPES", "chat:write,commands")
        resp = client.post("/integrations/slack/connect")
        assert resp.status_code == 200
        body = resp.json()
        assert "install_url" in body
        assert "slack.com/oauth/v2/authorize" in body["install_url"]
        assert "123.456" in body["install_url"]
        assert "signed-state-token" in body["install_url"]

    def test_returns_503_when_not_configured(self, client, monkeypatch):
        monkeypatch.setenv("SLACK_CLIENT_ID", "")
        resp = client.post("/integrations/slack/connect")
        assert resp.status_code == 503


# ── DELETE /integrations/slack ────────────────────────────────


class TestSlackDisconnect:
    @patch(
        "crewai_productfeature_planner.mongodb.slack_oauth.get_all_teams",
        return_value=[],
    )
    def test_404_when_no_integration(self, mock_teams, client):
        resp = client.delete("/integrations/slack")
        assert resp.status_code == 404

    @patch(
        "crewai_productfeature_planner.apis.integrations.router._revoke_slack_token",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.slack_oauth.delete_team",
        return_value=True,
    )
    @patch(
        "crewai_productfeature_planner.mongodb.slack_oauth.get_all_teams",
        return_value=[
            {"team_id": "T123", "team_name": "TestWorkspace", "access_token": "xoxb-test"},
        ],
    )
    @patch(
        "crewai_productfeature_planner.tools.slack_token_manager.invalidate",
    )
    def test_revokes_and_deletes(self, mock_invalidate, mock_teams, mock_delete, mock_revoke, client):
        resp = client.delete("/integrations/slack")
        assert resp.status_code == 204
        mock_revoke.assert_called_once_with("xoxb-test")
        mock_delete.assert_called_once_with("T123")

    @patch(
        "crewai_productfeature_planner.apis.integrations.router._revoke_slack_token",
        side_effect=Exception("Slack API error"),
    )
    @patch(
        "crewai_productfeature_planner.mongodb.slack_oauth.delete_team",
        return_value=True,
    )
    @patch(
        "crewai_productfeature_planner.mongodb.slack_oauth.get_all_teams",
        return_value=[
            {"team_id": "T123", "team_name": "TestWorkspace", "access_token": "xoxb-test"},
        ],
    )
    @patch(
        "crewai_productfeature_planner.tools.slack_token_manager.invalidate",
    )
    def test_deletes_even_when_revocation_fails(self, mock_invalidate, mock_teams, mock_delete, mock_revoke, client):
        resp = client.delete("/integrations/slack")
        assert resp.status_code == 204
        mock_delete.assert_called_once_with("T123")
