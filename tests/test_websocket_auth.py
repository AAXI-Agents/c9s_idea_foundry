"""Tests for WebSocket auth — _validate_ws_token.

Validates:
- Dev mode (SSO disabled) returns SYS_ADMIN claims with dev enterprise/org
- Missing token returns None when SSO enabled
- Valid token passes through introspection/decode pipeline
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── Dev mode (SSO disabled) ──────────────────────────────────


class TestDevMode:
    """When SSO_ENABLED != true, all connections pass with SYS_ADMIN claims."""

    @pytest.mark.asyncio
    async def test_sso_disabled_returns_sys_admin(self, monkeypatch):
        """SSO_ENABLED=false returns anonymous SYS_ADMIN."""
        monkeypatch.setenv("SSO_ENABLED", "false")
        monkeypatch.setenv("DEV_ENTERPRISE_ID", "test-ent")
        monkeypatch.setenv("DEV_ORGANIZATION_ID", "test-org")

        from crewai_productfeature_planner.apis.ideation._route_websocket import (
            _validate_ws_token,
        )

        result = await _validate_ws_token(None)
        assert result is not None
        assert result["user_id"] == "anonymous"
        assert result["roles"] == ["SYS_ADMIN"]
        assert result["enterprise_id"] == "test-ent"
        assert result["organization_id"] == "test-org"

    @pytest.mark.asyncio
    async def test_sso_disabled_ignores_token_value(self, monkeypatch):
        """Dev mode returns dev user regardless of token."""
        monkeypatch.setenv("SSO_ENABLED", "false")

        from crewai_productfeature_planner.apis.ideation._route_websocket import (
            _validate_ws_token,
        )

        result = await _validate_ws_token("some-token-value")
        assert result is not None
        assert result["user_id"] == "anonymous"

    @pytest.mark.asyncio
    async def test_sso_unset_defaults_to_dev_mode(self, monkeypatch):
        """If SSO_ENABLED is not set at all, default to dev mode."""
        monkeypatch.delenv("SSO_ENABLED", raising=False)

        from crewai_productfeature_planner.apis.ideation._route_websocket import (
            _validate_ws_token,
        )

        result = await _validate_ws_token(None)
        assert result is not None
        assert result["roles"] == ["SYS_ADMIN"]


# ── SSO enabled — token required ──────────────────────────────


class TestSSOEnabled:
    """When SSO_ENABLED=true, token must be provided and validated."""

    @pytest.mark.asyncio
    async def test_missing_token_returns_none(self, monkeypatch):
        """No token returns None — WebSocket should close."""
        monkeypatch.setenv("SSO_ENABLED", "true")

        from crewai_productfeature_planner.apis.ideation._route_websocket import (
            _validate_ws_token,
        )

        result = await _validate_ws_token(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_token_returns_none(self, monkeypatch):
        """Empty string token returns None."""
        monkeypatch.setenv("SSO_ENABLED", "true")

        from crewai_productfeature_planner.apis.ideation._route_websocket import (
            _validate_ws_token,
        )

        result = await _validate_ws_token("")
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_token_introspected(self, monkeypatch):
        """Valid token resolves via remote introspection."""
        monkeypatch.setenv("SSO_ENABLED", "true")

        expected = {
            "user_id": "u123",
            "roles": ["ENT_ADMIN"],
            "enterprise_id": "e1",
            "organization_id": "o1",
        }

        with patch(
            "crewai_productfeature_planner.apis.sso_auth._introspect_remotely",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_introspect, patch(
            "crewai_productfeature_planner.apis.sso_auth._decode_jwt_locally",
        ) as mock_decode:
            from crewai_productfeature_planner.apis.ideation._route_websocket import (
                _validate_ws_token,
            )

            result = await _validate_ws_token("valid-jwt-token")
            assert result == expected
            mock_introspect.assert_called_once_with("valid-jwt-token")
            mock_decode.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_to_local_decode(self, monkeypatch):
        """Falls back to local decode if introspection returns None."""
        monkeypatch.setenv("SSO_ENABLED", "true")

        expected = {
            "user_id": "u456",
            "roles": ["USER"],
            "enterprise_id": "e2",
            "organization_id": "o2",
        }

        with patch(
            "crewai_productfeature_planner.apis.sso_auth._introspect_remotely",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "crewai_productfeature_planner.apis.sso_auth._decode_jwt_locally",
            return_value=expected,
        ) as mock_decode:
            from crewai_productfeature_planner.apis.ideation._route_websocket import (
                _validate_ws_token,
            )

            result = await _validate_ws_token("another-token")
            assert result == expected
            mock_decode.assert_called_once_with("another-token")
