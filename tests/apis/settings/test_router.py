"""Tests for the enterprise settings router (GET/PATCH /settings)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app
from crewai_productfeature_planner.apis.admin_deps import require_enterprise_admin
from crewai_productfeature_planner.apis.sso_auth import require_sso_user

_SETTINGS_REPO = "crewai_productfeature_planner.apis.settings.router"


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


class TestGetSettings:
    """GET /settings tests."""

    def test_returns_settings(self, admin_client):
        mock_settings = {
            "enterprise_id": "ent-test",
            "workspace_name": "Test Corp",
            "log_level": "INFO",
            "agent_toggles": {},
            "agent_concurrency": 3,
            "agent_recommendations": 3,
            "agent_suggestions": 3,
            "agent_flow_iteration": 5,
            "enterprise_seat_capacity": 10,
            "github_repo_enabled": False,
            "agent_label_mappings": [],
        }
        with patch(f"{_SETTINGS_REPO}.get_enterprise_settings", return_value=mock_settings):
            resp = admin_client.get("/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["settings"]["workspace_name"] == "Test Corp"
        assert data["settings"]["enterprise_id"] == "ent-test"

    def test_regular_user_can_read(self, user_client):
        """Any authenticated user can GET settings."""
        mock_settings = {"enterprise_id": "ent-test", "workspace_name": "Corp"}
        with patch(f"{_SETTINGS_REPO}.get_enterprise_settings", return_value=mock_settings):
            resp = user_client.get("/settings")
        assert resp.status_code == 200

    def test_no_enterprise_id_returns_403(self):
        """User without enterprise_id gets 403."""
        user = _regular_user()
        user["enterprise_id"] = ""
        app.dependency_overrides[require_sso_user] = lambda: user
        with TestClient(app) as c:
            resp = c.get("/settings")
        app.dependency_overrides.clear()
        assert resp.status_code == 403


class TestPatchSettings:
    """PATCH /settings tests."""

    def test_updates_settings(self, admin_client):
        updated = {
            "enterprise_id": "ent-test",
            "workspace_name": "New Name",
            "log_level": "DEBUG",
            "agent_concurrency": 5,
        }
        with patch(f"{_SETTINGS_REPO}.update_enterprise_settings", return_value=updated):
            resp = admin_client.patch(
                "/settings",
                json={"workspace_name": "New Name", "log_level": "DEBUG", "agent_concurrency": 5},
            )
        assert resp.status_code == 200
        assert resp.json()["settings"]["workspace_name"] == "New Name"

    def test_regular_user_cannot_patch(self, user_client):
        """Non-admin users get 403 on PATCH."""
        resp = user_client.patch("/settings", json={"workspace_name": "Hack"})
        assert resp.status_code == 403

    def test_empty_patch_returns_422(self, admin_client):
        """Empty body returns 422."""
        resp = admin_client.patch("/settings", json={})
        assert resp.status_code == 422

    def test_invalid_log_level_returns_422(self, admin_client):
        """Invalid log_level returns 422."""
        with patch(f"{_SETTINGS_REPO}.update_enterprise_settings"):
            resp = admin_client.patch("/settings", json={"log_level": "TRACE"})
        assert resp.status_code == 422

    def test_concurrency_validation(self, admin_client):
        """agent_concurrency must be between 1 and 20."""
        resp = admin_client.patch("/settings", json={"agent_concurrency": 0})
        assert resp.status_code == 422
        resp = admin_client.patch("/settings", json={"agent_concurrency": 25})
        assert resp.status_code == 422

    def test_agent_label_mappings(self, admin_client):
        updated = {"enterprise_id": "ent-test", "agent_label_mappings": [{"jira_label": "bug", "agent_slug": "qa", "display_name": "QA"}]}
        with patch(f"{_SETTINGS_REPO}.update_enterprise_settings", return_value=updated):
            resp = admin_client.patch(
                "/settings",
                json={"agent_label_mappings": [{"jira_label": "bug", "agent_slug": "qa", "display_name": "QA"}]},
            )
        assert resp.status_code == 200
