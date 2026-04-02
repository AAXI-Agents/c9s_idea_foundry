"""Tests for GET /integrations/status endpoint."""

from unittest.mock import patch

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


class TestIntegrationStatus:
    """Tests for GET /integrations/status."""

    def test_no_creds_configured(self, client, monkeypatch):
        """Should return not configured when no env vars set."""
        monkeypatch.delenv("ATLASSIAN_BASE_URL", raising=False)
        monkeypatch.delenv("ATLASSIAN_USERNAME", raising=False)
        monkeypatch.delenv("ATLASSIAN_API_TOKEN", raising=False)
        monkeypatch.delenv("JIRA_PROJECT_KEY", raising=False)

        resp = client.get("/integrations/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["confluence"]["configured"] is False
        assert body["jira"]["configured"] is False
        assert body["confluence"]["base_url"] == ""
        assert body["jira"]["project_key"] == ""

    def test_confluence_only(self, client, monkeypatch):
        """Should show Confluence configured but not Jira when no project key."""
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://myco.atlassian.net")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret-token")
        monkeypatch.delenv("JIRA_PROJECT_KEY", raising=False)

        resp = client.get("/integrations/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["confluence"]["configured"] is True
        assert "myco.atlassian.net" in body["confluence"]["base_url"]
        assert body["jira"]["configured"] is False

    def test_both_configured(self, client, monkeypatch):
        """Should show both configured when all vars set."""
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://myco.atlassian.net")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret-token")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "MCR")

        resp = client.get("/integrations/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["confluence"]["configured"] is True
        assert body["jira"]["configured"] is True
        assert body["jira"]["project_key"] == "MCR"

    def test_base_url_masked(self, client, monkeypatch):
        """Should mask the base URL to only show scheme + hostname."""
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://myco.atlassian.net/wiki")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret-token")
        monkeypatch.delenv("JIRA_PROJECT_KEY", raising=False)

        resp = client.get("/integrations/status")
        body = resp.json()
        # Should not include /wiki path
        assert body["confluence"]["base_url"] == "https://myco.atlassian.net"
