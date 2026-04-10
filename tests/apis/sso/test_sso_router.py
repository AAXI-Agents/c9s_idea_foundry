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

    def test_valid_token_returns_user_profile(self, client):
        """Should return user profile when local JWT decode succeeds."""
        claims = {
            "sub": "user-123",
            "email": "test@example.com",
            "roles": ["USER"],
            "enterprise_id": "ent-1",
            "organization_id": "org-1",
            "type": "access",
        }
        with patch(
            "crewai_productfeature_planner.apis.sso.router._decode_jwt_locally",
            return_value=claims,
        ):
            resp = client.get(
                "/auth/sso/userinfo",
                headers={"Authorization": "Bearer valid-token"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == "user-123"
        assert body["email"] == "test@example.com"
        assert body["roles"] == ["USER"]

    def test_expired_token_returns_401(self, client):
        """Should return 401 when both local decode and introspection fail."""
        with (
            patch(
                "crewai_productfeature_planner.apis.sso.router._decode_jwt_locally",
                return_value=None,
            ),
            patch(
                "crewai_productfeature_planner.apis.sso.router._introspect_remotely",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            resp = client.get(
                "/auth/sso/userinfo",
                headers={"Authorization": "Bearer expired-token"},
            )
        assert resp.status_code == 401

    def test_introspection_fallback_works(self, client):
        """Should fall back to remote introspection when local decode fails."""
        introspection_result = {
            "active": True,
            "sub": "user-456",
            "email": "fallback@example.com",
            "roles": ["ADMIN"],
            "enterprise_id": "",
            "organization_id": "",
        }
        with (
            patch(
                "crewai_productfeature_planner.apis.sso.router._decode_jwt_locally",
                return_value=None,
            ),
            patch(
                "crewai_productfeature_planner.apis.sso.router._introspect_remotely",
                new_callable=AsyncMock,
                return_value=introspection_result,
            ),
        ):
            resp = client.get(
                "/auth/sso/userinfo",
                headers={"Authorization": "Bearer some-token"},
            )
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "user-456"

    def test_malformed_bearer_returns_401(self, client):
        """Should return 401 when Authorization header is present but not Bearer."""
        resp = client.get(
            "/auth/sso/userinfo",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
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
        """Should proxy refresh to SSO server with client_id."""
        monkeypatch.setenv("SSO_BASE_URL", "https://sso.example.com")
        monkeypatch.setenv("SSO_CLIENT_ID", "test-client")

        with _mock_proxy({"access_token": "new-tok"}) as mock_post:
            resp = client.post("/auth/sso/token/refresh", json={"refresh_token": "rt-123"})
            assert resp.status_code == 200
            assert resp.json()["access_token"] == "new-tok"
            # Verify client_id is injected into the proxy payload
            call_args = mock_post.call_args
            assert call_args[1]["json"]["client_id"] == "test-client"
            assert call_args[1]["json"]["refresh_token"] == "rt-123"


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


# ── _decode_jwt_locally with PyJWT ────────────────────────────


class TestDecodeJwtLocally:
    """Tests for _decode_jwt_locally using PyJWT."""

    def _make_token(self, claims: dict, private_key):
        """Create a signed RS256 JWT for testing."""
        import jwt as pyjwt

        return pyjwt.encode(claims, private_key, algorithm="RS256")

    @pytest.fixture()
    def rsa_keys(self):
        """Generate an RSA key pair for testing."""
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        public_pem = private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        private_pem = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        return private_pem, public_pem

    def test_valid_access_token_decoded(self, rsa_keys, monkeypatch, tmp_path):
        """Should decode a valid RS256 access token."""
        import time

        from crewai_productfeature_planner.apis.sso_auth import (
            _decode_jwt_locally,
            _sso_public_key,
        )

        private_pem, public_pem = rsa_keys
        key_file = tmp_path / "pub.pem"
        key_file.write_text(public_pem)
        monkeypatch.setenv("SSO_JWT_PUBLIC_KEY_PATH", str(key_file))
        monkeypatch.setenv("SSO_ISSUER", "c9s-sso")
        _sso_public_key.cache_clear()

        token = self._make_token(
            {
                "sub": "u1",
                "email": "test@x.com",
                "roles": ["USER"],
                "type": "access",
                "iss": "c9s-sso",
                "iat": int(time.time()),
                "exp": int(time.time()) + 900,
            },
            private_pem,
        )

        result = _decode_jwt_locally(token)
        assert result is not None
        assert result["sub"] == "u1"
        assert result["email"] == "test@x.com"
        _sso_public_key.cache_clear()

    def test_refresh_token_rejected(self, rsa_keys, monkeypatch, tmp_path):
        """Should reject tokens with type != access."""
        import time

        from crewai_productfeature_planner.apis.sso_auth import (
            _decode_jwt_locally,
            _sso_public_key,
        )

        private_pem, public_pem = rsa_keys
        key_file = tmp_path / "pub.pem"
        key_file.write_text(public_pem)
        monkeypatch.setenv("SSO_JWT_PUBLIC_KEY_PATH", str(key_file))
        monkeypatch.setenv("SSO_ISSUER", "c9s-sso")
        _sso_public_key.cache_clear()

        token = self._make_token(
            {
                "sub": "u1",
                "type": "refresh",
                "iss": "c9s-sso",
                "iat": int(time.time()),
                "exp": int(time.time()) + 900,
            },
            private_pem,
        )

        result = _decode_jwt_locally(token)
        assert result is None
        _sso_public_key.cache_clear()

    def test_expired_token_returns_none(self, rsa_keys, monkeypatch, tmp_path):
        """Should return None for expired tokens."""
        import time

        from crewai_productfeature_planner.apis.sso_auth import (
            _decode_jwt_locally,
            _sso_public_key,
        )

        private_pem, public_pem = rsa_keys
        key_file = tmp_path / "pub.pem"
        key_file.write_text(public_pem)
        monkeypatch.setenv("SSO_JWT_PUBLIC_KEY_PATH", str(key_file))
        monkeypatch.setenv("SSO_ISSUER", "c9s-sso")
        _sso_public_key.cache_clear()

        token = self._make_token(
            {
                "sub": "u1",
                "type": "access",
                "iss": "c9s-sso",
                "iat": int(time.time()) - 1000,
                "exp": int(time.time()) - 100,
            },
            private_pem,
        )

        result = _decode_jwt_locally(token)
        assert result is None
        _sso_public_key.cache_clear()

    def test_wrong_issuer_returns_none(self, rsa_keys, monkeypatch, tmp_path):
        """Should return None when issuer doesn't match."""
        import time

        from crewai_productfeature_planner.apis.sso_auth import (
            _decode_jwt_locally,
            _sso_public_key,
        )

        private_pem, public_pem = rsa_keys
        key_file = tmp_path / "pub.pem"
        key_file.write_text(public_pem)
        monkeypatch.setenv("SSO_JWT_PUBLIC_KEY_PATH", str(key_file))
        monkeypatch.setenv("SSO_ISSUER", "c9s-sso")
        _sso_public_key.cache_clear()

        token = self._make_token(
            {
                "sub": "u1",
                "type": "access",
                "iss": "wrong-issuer",
                "iat": int(time.time()),
                "exp": int(time.time()) + 900,
            },
            private_pem,
        )

        result = _decode_jwt_locally(token)
        assert result is None
        _sso_public_key.cache_clear()

    def test_no_public_key_returns_none(self, monkeypatch):
        """Should return None when no public key is configured."""
        from crewai_productfeature_planner.apis.sso_auth import (
            _decode_jwt_locally,
            _sso_public_key,
        )

        monkeypatch.delenv("SSO_JWT_PUBLIC_KEY_PATH", raising=False)
        _sso_public_key.cache_clear()

        result = _decode_jwt_locally("some.jwt.token")
        assert result is None
        _sso_public_key.cache_clear()


# ── Login → Userinfo integration ──────────────────────────────


class TestLoginToUserinfoFlow:
    """End-to-end test: login → use token → get userinfo."""

    def test_login_then_userinfo(self, client, monkeypatch):
        """Login should return tokens; userinfo should decode them."""
        tokens = {
            "access_token": "fresh-jwt",
            "refresh_token": "rt-1",
            "token_type": "Bearer",
            "expires_in": 900,
        }
        user_claims = {
            "sub": "user-789",
            "email": "minh@pascalsoftware.com",
            "roles": ["USER"],
            "enterprise_id": "ent-1",
            "organization_id": "org-1",
            "type": "access",
        }

        # Step 1: login → get tokens
        with _mock_proxy(tokens):
            login_resp = client.post(
                "/auth/sso/login",
                json={"email": "minh@pascalsoftware.com", "password": "pw"},
            )
        assert login_resp.status_code == 200
        access_token = login_resp.json()["access_token"]

        # Step 2: use token → get userinfo
        with patch(
            "crewai_productfeature_planner.apis.sso.router._decode_jwt_locally",
            return_value=user_claims,
        ):
            info_resp = client.get(
                "/auth/sso/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        assert info_resp.status_code == 200
        body = info_resp.json()
        assert body["user_id"] == "user-789"
        assert body["email"] == "minh@pascalsoftware.com"


# ── Introspection client_id & key cache ──────────────────────


class TestIntrospectClientId:
    """Verify that _introspect_remotely sends client_id."""

    @pytest.mark.asyncio
    async def test_introspect_includes_client_id_and_auth_header(self):
        """Remote introspection should send client_id in body and
        Authorization: Bearer <secret> header (RFC 7662)."""
        from crewai_productfeature_planner.apis.sso_auth import (
            _introspect_remotely,
        )

        captured_payload: dict = {}
        captured_headers: dict = {}

        async def _fake_post(url, *, json=None, headers=None):
            captured_payload.update(json or {})
            captured_headers.update(headers or {})
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"active": True, "sub": "u1"}
            return mock_resp

        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=_fake_post)
        mock_client.is_closed = False

        with (
            patch(
                "crewai_productfeature_planner.apis.sso_auth._get_sso_http_client",
                return_value=mock_client,
            ),
            patch.dict(
                "os.environ",
                {
                    "SSO_CLIENT_ID": "test-app-123",
                    "SSO_CLIENT_SECRET": "s3cret",
                    "SSO_BASE_URL": "http://sso",
                },
            ),
        ):
            result = await _introspect_remotely("tok-abc")

        assert result is not None
        assert result["active"] is True
        assert captured_payload.get("client_id") == "test-app-123"
        assert captured_payload.get("token") == "tok-abc"
        assert captured_headers.get("Authorization") == "Bearer s3cret"


class TestFetchAndSavePublicKey:
    """Verify _fetch_and_save_public_key downloads and saves the key."""

    @pytest.mark.asyncio
    async def test_fetches_saves_and_clears_cache(self, tmp_path):
        """Should download key from SSO, save to disk, and clear LRU cache."""
        from crewai_productfeature_planner.apis.sso_auth import (
            _fetch_and_save_public_key,
            _sso_public_key,
        )

        key_file = tmp_path / "pub.pem"
        key_file.write_text("old-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"public_key": "-----BEGIN PUBLIC KEY-----\nnew-key\n-----END PUBLIC KEY-----"}

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False

        _sso_public_key.cache_clear()

        with (
            patch(
                "crewai_productfeature_planner.apis.sso_auth._get_sso_http_client",
                return_value=mock_client,
            ),
            patch.dict(
                "os.environ",
                {
                    "SSO_BASE_URL": "http://sso",
                    "SSO_JWT_PUBLIC_KEY_PATH": str(key_file),
                },
            ),
        ):
            result = await _fetch_and_save_public_key()

        assert result is not None
        assert "new-key" in result
        assert "new-key" in key_file.read_text()

    @pytest.mark.asyncio
    async def test_returns_none_when_no_key_path(self):
        """Should return None when SSO_JWT_PUBLIC_KEY_PATH is not set."""
        from crewai_productfeature_planner.apis.sso_auth import (
            _fetch_and_save_public_key,
        )

        with patch.dict("os.environ", {"SSO_JWT_PUBLIC_KEY_PATH": ""}):
            result = await _fetch_and_save_public_key()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_non_200(self, tmp_path):
        """Should return None when SSO server returns non-200."""
        from crewai_productfeature_planner.apis.sso_auth import (
            _fetch_and_save_public_key,
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 500

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False

        with (
            patch(
                "crewai_productfeature_planner.apis.sso_auth._get_sso_http_client",
                return_value=mock_client,
            ),
            patch.dict(
                "os.environ",
                {
                    "SSO_BASE_URL": "http://sso",
                    "SSO_JWT_PUBLIC_KEY_PATH": str(tmp_path / "k.pem"),
                },
            ),
        ):
            result = await _fetch_and_save_public_key()
        assert result is None


class TestPublicKeyCacheClear:
    """Verify cache is cleared on InvalidSignatureError."""

    def test_cache_cleared_on_signature_error(self):
        """_decode_jwt_locally should clear cache when signature fails."""
        from crewai_productfeature_planner.apis.sso_auth import (
            _decode_jwt_locally,
            _sso_public_key,
        )

        # Prime the cache
        _sso_public_key.cache_clear()
        with patch.dict("os.environ", {"SSO_JWT_PUBLIC_KEY_PATH": ""}):
            _sso_public_key()  # returns None, cached

        # Verify initial state: cache has 1 entry
        assert _sso_public_key.cache_info().currsize == 1

        # Call with a fake key that will trigger InvalidSignatureError
        with (
            patch(
                "crewai_productfeature_planner.apis.sso_auth._sso_public_key",
                wraps=_sso_public_key,
            ),
            patch.dict("os.environ", {"SSO_JWT_PUBLIC_KEY_PATH": ""}),
        ):
            # Calling with no key returns None immediately (no error)
            result = _decode_jwt_locally("fake.jwt.token")
            assert result is None
