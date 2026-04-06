"""Tests for SSO authentication router — /auth/sso/* endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app


def _mock_proxy(response_json: dict, status_code: int = 200):
    """Return a patch context that replaces _sso_proxy_post with an async mock."""
    async def _fake_proxy(*args, **kwargs):
        return JSONResponse(response_json, status_code=status_code)
    return patch(
        "crewai_productfeature_planner.apis.sso.router._sso_proxy_post",
        side_effect=_fake_proxy,
    )


def _mock_proxy_error(exc: Exception | None = None):
    """Return a patch context simulating an SSO proxy failure (502)."""
    async def _fake_proxy(*args, **kwargs):
        return JSONResponse(
            {"error": f"SSO server unreachable: {exc or 'Connection refused'}"},
            status_code=502,
        )
    return patch(
        "crewai_productfeature_planner.apis.sso.router._sso_proxy_post",
        side_effect=_fake_proxy,
    )


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


# ── GET /auth/sso/login ──────────────────────────────────────


class TestSSOLoginRedirect:
    """Tests for GET /auth/sso/login (OAuth2 redirect)."""

    def test_redirects_when_client_id_set(self, client, monkeypatch):
        """Should redirect to SSO authorize URL when SSO_CLIENT_ID is set."""
        monkeypatch.setenv("SSO_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("SSO_BASE_URL", "https://sso.example.com")
        resp = client.get("/auth/sso/login", follow_redirects=False)
        assert resp.status_code == 307
        location = resp.headers["location"]
        assert "sso.example.com/sso/oauth/authorize" in location
        assert "client_id=test-client-id" in location
        assert "response_type=code" in location

    def test_returns_503_when_no_client_id(self, client, monkeypatch):
        """Should return 503 when SSO_CLIENT_ID is not configured."""
        monkeypatch.delenv("SSO_CLIENT_ID", raising=False)
        resp = client.get("/auth/sso/login", follow_redirects=False)
        assert resp.status_code == 503
        assert "SSO_CLIENT_ID" in resp.json()["error"]


# ── POST /auth/sso/login ─────────────────────────────────────


class TestSSODirectLogin:
    """Tests for POST /auth/sso/login (email/password → tokens)."""

    def test_missing_email_returns_400(self, client):
        """Should return 400 when email is missing."""
        resp = client.post("/auth/sso/login", json={"password": "test"})
        assert resp.status_code == 400
        assert "email" in resp.json()["error"]

    def test_missing_password_returns_400(self, client):
        """Should return 400 when password is missing."""
        resp = client.post("/auth/sso/login", json={"email": "a@b.com"})
        assert resp.status_code == 400
        assert "password" in resp.json()["error"]

    def test_invalid_json_returns_400(self, client):
        """Should return 400 for invalid JSON body."""
        resp = client.post(
            "/auth/sso/login",
            content=b"not-json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400

    def test_proxies_to_sso_server(self, client, monkeypatch):
        """Should proxy login request to SSO server."""
        monkeypatch.setenv("SSO_BASE_URL", "https://sso.example.com")
        monkeypatch.setenv("SSO_CLIENT_ID", "test-client")

        with _mock_proxy({"access_token": "tok", "refresh_token": "rt"}) as mock_post:
            resp = client.post("/auth/sso/login", json={"email": "a@b.com", "password": "pass"})
            assert resp.status_code == 200
            assert resp.json()["access_token"] == "tok"
            # Verify the proxy was called with the login path
            call_args = mock_post.call_args
            assert "/sso/auth/login" in call_args[0][0]
            assert call_args[1]["json"]["client_id"] == "test-client"

    def test_returns_502_when_sso_unreachable(self, client, monkeypatch):
        """Should return 502 when SSO server is unreachable."""
        monkeypatch.setenv("SSO_BASE_URL", "https://sso.example.com")
        monkeypatch.setenv("SSO_CLIENT_ID", "test-client")

        with _mock_proxy_error():
            resp = client.post("/auth/sso/login", json={"email": "a@b.com", "password": "pass"})
            assert resp.status_code == 502
            assert "unreachable" in resp.json()["error"]


# ── POST /auth/sso/login/verify-2fa ──────────────────────────


class TestSSOLoginVerify2FA:
    """Tests for POST /auth/sso/login/verify-2fa."""

    def test_missing_fields_returns_400(self, client):
        """Should return 400 when required fields are missing."""
        resp = client.post("/auth/sso/login/verify-2fa", json={"email": "a@b.com"})
        assert resp.status_code == 400

    def test_proxies_to_sso(self, client, monkeypatch):
        """Should proxy 2FA verification to SSO server."""
        monkeypatch.setenv("SSO_BASE_URL", "https://sso.example.com")

        with _mock_proxy({"access_token": "tok"}):
            resp = client.post("/auth/sso/login/verify-2fa", json={
                "email": "a@b.com", "login_token": "lt-123", "code": "123456",
            })
            assert resp.status_code == 200


# ── GET /auth/sso/callback ───────────────────────────────────


class TestSSOCallback:
    """Tests for GET /auth/sso/callback."""

    def test_error_param_returns_400(self, client):
        """Should return 400 when error param is present."""
        resp = client.get("/auth/sso/callback?error=access_denied&error_description=User+denied")
        assert resp.status_code == 400
        assert "SSO Sign-In Failed" in resp.text

    def test_state_mismatch_returns_400(self, client):
        """Should return 400 on CSRF state mismatch."""
        resp = client.get("/auth/sso/callback?code=abc&state=wrong")
        assert resp.status_code == 400
        assert "CSRF" in resp.text


# ── GET /auth/sso/status ─────────────────────────────────────


class TestSSOStatus:
    """Tests for GET /auth/sso/status."""

    def test_unauthenticated_no_sso_client(self, client, monkeypatch):
        """Should return not authenticated when no SSO config."""
        monkeypatch.delenv("SSO_CLIENT_ID", raising=False)
        resp = client.get("/auth/sso/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["authenticated"] is False

    def test_unauthenticated_with_sso_client(self, client, monkeypatch):
        """Should return sso_configured=True when client ID set."""
        monkeypatch.setenv("SSO_CLIENT_ID", "test-client")
        resp = client.get("/auth/sso/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["authenticated"] is False
        assert body["sso_configured"] is True


# ── GET /auth/sso/userinfo ───────────────────────────────────


class TestSSOUserinfo:
    """Tests for GET /auth/sso/userinfo."""

    def test_missing_bearer_returns_401(self, client):
        """Should return 401 when no Bearer token provided."""
        resp = client.get("/auth/sso/userinfo")
        assert resp.status_code == 401


# ── POST /auth/sso/register ──────────────────────────────────


class TestSSORegister:
    """Tests for POST /auth/sso/register."""

    def test_missing_email_returns_400(self, client):
        """Should return 400 when email is missing."""
        resp = client.post("/auth/sso/register", json={"password": "test"})
        assert resp.status_code == 400

    def test_missing_password_returns_400(self, client):
        """Should return 400 when password is missing."""
        resp = client.post("/auth/sso/register", json={"email": "a@b.com"})
        assert resp.status_code == 400


# ── GET /auth/sso/register ───────────────────────────────────


class TestSSORegisterRedirect:
    """Tests for GET /auth/sso/register (redirect)."""

    def test_redirects_to_sso_register(self, client, monkeypatch):
        """Should redirect to SSO registration page."""
        monkeypatch.setenv("SSO_BASE_URL", "https://sso.example.com")
        resp = client.get("/auth/sso/register", follow_redirects=False)
        assert resp.status_code == 307
        location = resp.headers["location"]
        assert "sso.example.com/sso/users/register" in location


# ── POST /auth/sso/password-reset ─────────────────────────────


class TestSSOPasswordReset:
    """Tests for POST /auth/sso/password-reset."""

    def test_missing_email_returns_400(self, client):
        """Should return 400 when email is missing."""
        resp = client.post("/auth/sso/password-reset", json={})
        assert resp.status_code == 400

    def test_proxies_to_sso(self, client, monkeypatch):
        """Should proxy to SSO server."""
        monkeypatch.setenv("SSO_BASE_URL", "https://sso.example.com")

        with _mock_proxy({"status": "sent"}):
            resp = client.post("/auth/sso/password-reset", json={"email": "a@b.com"})
            assert resp.status_code == 200


# ── POST /auth/sso/password-reset/confirm ─────────────────────


class TestSSOPasswordResetConfirm:
    """Tests for POST /auth/sso/password-reset/confirm."""

    def test_missing_fields_returns_400(self, client):
        """Should return 400 when required fields missing."""
        resp = client.post("/auth/sso/password-reset/confirm", json={"email": "a@b.com"})
        assert resp.status_code == 400


# ── POST /auth/sso/token/refresh ──────────────────────────────


class TestSSOTokenRefresh:
    """Tests for POST /auth/sso/token/refresh."""

    def test_missing_refresh_token_returns_400(self, client):
        """Should return 400 when refresh_token is missing."""
        resp = client.post("/auth/sso/token/refresh", json={})
        assert resp.status_code == 400

    def test_proxies_to_sso(self, client, monkeypatch):
        """Should proxy refresh to SSO server."""
        monkeypatch.setenv("SSO_BASE_URL", "https://sso.example.com")

        with _mock_proxy({"access_token": "new-tok"}):
            resp = client.post("/auth/sso/token/refresh", json={"refresh_token": "rt-123"})
            assert resp.status_code == 200
            assert resp.json()["access_token"] == "new-tok"


# ── POST /auth/sso/reauth ────────────────────────────────────


class TestSSOReauth:
    """Tests for POST /auth/sso/reauth."""

    def test_missing_password_returns_400(self, client):
        """Should return 400 when password is missing."""
        resp = client.post("/auth/sso/reauth", json={})
        assert resp.status_code == 400


# ── POST /auth/sso/reauth/verify-2fa ─────────────────────────


class TestSSOReauthVerify2FA:
    """Tests for POST /auth/sso/reauth/verify-2fa."""

    def test_missing_fields_returns_400(self, client):
        """Should return 400 when fields are missing."""
        resp = client.post("/auth/sso/reauth/verify-2fa", json={"code": "123"})
        assert resp.status_code == 400


# ── POST /auth/sso/google ────────────────────────────────────


class TestSSOGoogle:
    """Tests for POST /auth/sso/google."""

    def test_missing_id_token_returns_400(self, client):
        """Should return 400 when id_token is missing."""
        resp = client.post("/auth/sso/google", json={})
        assert resp.status_code == 400


# ── POST /auth/sso/register/verify-2fa ────────────────────────


class TestSSORegisterVerify2FA:
    """Tests for POST /auth/sso/register/verify-2fa."""

    def test_missing_fields_returns_400(self, client):
        """Should return 400 when fields are missing."""
        resp = client.post("/auth/sso/register/verify-2fa", json={"email": "a@b.com"})
        assert resp.status_code == 400


# ── POST /auth/sso/register/resend-2fa ────────────────────────


class TestSSORegisterResend2FA:
    """Tests for POST /auth/sso/register/resend-2fa."""

    def test_missing_email_returns_400(self, client):
        """Should return 400 when email is missing."""
        resp = client.post("/auth/sso/register/resend-2fa", json={})
        assert resp.status_code == 400


# ── POST /auth/sso/logout & /auth/sso/logout-all ─────────────


class TestSSOLogout:
    """Tests for POST /auth/sso/logout and /auth/sso/logout-all."""

    def test_logout_proxies_to_sso(self, client, monkeypatch):
        """Should proxy logout to SSO server."""
        monkeypatch.setenv("SSO_BASE_URL", "https://sso.example.com")

        with _mock_proxy({"status": "ok"}):
            resp = client.post(
                "/auth/sso/logout",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 200

    def test_logout_all_proxies_to_sso(self, client, monkeypatch):
        """Should proxy logout-all to SSO server."""
        monkeypatch.setenv("SSO_BASE_URL", "https://sso.example.com")

        with _mock_proxy({"status": "ok"}):
            resp = client.post(
                "/auth/sso/logout-all",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 200
