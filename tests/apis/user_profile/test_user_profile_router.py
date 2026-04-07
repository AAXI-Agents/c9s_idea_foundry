"""Tests for user profile endpoints — GET/PATCH /user/profile."""

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


# ── GET /user/profile ────────────────────────────────────────


class TestGetProfile:
    """Tests for GET /user/profile."""

    def test_returns_profile_with_sso_note(self, client):
        """Response should include profile_managed_by and sso_profile_note."""
        with patch(
            "crewai_productfeature_planner.apis.user_profile.router.get_preferences",
            return_value=None,
        ):
            resp = client.get("/user/profile")
        assert resp.status_code == 200
        body = resp.json()
        assert body["profile_managed_by"] == "sso"
        assert body["sso_profile_note"] == "Profile managed by your SSO provider."

    def test_returns_sso_identity_fields(self, client):
        """Response should include SSO-managed identity fields."""
        with patch(
            "crewai_productfeature_planner.apis.user_profile.router.get_preferences",
            return_value=None,
        ):
            resp = client.get("/user/profile")
        assert resp.status_code == 200
        body = resp.json()
        assert "user_id" in body
        assert "email" in body
        assert "sso_display_name" in body

    def test_merges_local_preferences(self, client):
        """Response should merge SSO identity with local preferences."""
        prefs = {
            "display_name": "Custom Name",
            "timezone": "Asia/Singapore",
            "notification_preferences": {"web": True, "slack": False},
        }
        with patch(
            "crewai_productfeature_planner.apis.user_profile.router.get_preferences",
            return_value=prefs,
        ):
            resp = client.get("/user/profile")
        assert resp.status_code == 200
        body = resp.json()
        assert body["display_name"] == "Custom Name"
        assert body["timezone"] == "Asia/Singapore"
        assert body["notification_preferences"]["web"] is True
        assert body["notification_preferences"]["slack"] is False


# ── PATCH /user/profile ──────────────────────────────────────


class TestUpdateProfile:
    """Tests for PATCH /user/profile."""

    def test_update_returns_sso_note(self, client):
        """PATCH response should still include SSO management note."""
        with patch(
            "crewai_productfeature_planner.apis.user_profile.router.upsert_preferences",
            return_value={"display_name": "New Name"},
        ):
            resp = client.patch(
                "/user/profile",
                json={"display_name": "New Name"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["profile_managed_by"] == "sso"
        assert body["sso_profile_note"] == "Profile managed by your SSO provider."

    def test_empty_update_returns_current(self, client):
        """PATCH with no fields should return current profile."""
        with patch(
            "crewai_productfeature_planner.apis.user_profile.router.get_preferences",
            return_value=None,
        ):
            resp = client.patch("/user/profile", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["profile_managed_by"] == "sso"
