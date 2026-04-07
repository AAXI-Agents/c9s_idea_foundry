"""Tests for SSO auth dependency — require_sso_user claim extraction."""

from unittest.mock import patch

import pytest
from starlette.requests import Request

from crewai_productfeature_planner.apis.sso_auth import require_sso_user


@pytest.fixture(autouse=True)
def _enable_sso(monkeypatch):
    monkeypatch.setenv("SSO_ENABLED", "true")
    monkeypatch.setenv("SSO_BASE_URL", "https://sso.example.com")


def _make_request() -> Request:
    """Build a minimal Starlette Request with a dummy Bearer token."""
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [(b"authorization", b"Bearer fake-token")],
    })


class TestDisplayNameExtraction:
    """Verify require_sso_user pulls display_name from JWT claims."""

    @pytest.mark.asyncio
    async def test_uses_display_name_claim_when_present(self, monkeypatch):
        """Should use 'display_name' from claims when available."""
        claims = {
            "sub": "user-123",
            "email": "alice@example.com",
            "display_name": "Alice Smith",
            "roles": ["user"],
            "type": "access",
        }
        with patch(
            "crewai_productfeature_planner.apis.sso_auth._decode_jwt_locally",
            return_value=claims,
        ):
            user = await require_sso_user(_make_request())
        assert user["display_name"] == "Alice Smith"

    @pytest.mark.asyncio
    async def test_falls_back_to_email_when_no_display_name(self, monkeypatch):
        """Should fall back to email when display_name is not in claims."""
        claims = {
            "sub": "user-456",
            "email": "bob@example.com",
            "roles": ["user"],
            "type": "access",
        }
        with patch(
            "crewai_productfeature_planner.apis.sso_auth._decode_jwt_locally",
            return_value=claims,
        ):
            user = await require_sso_user(_make_request())
        assert user["display_name"] == "bob@example.com"
