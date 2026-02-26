"""Tests for the Slack OAuth callback router."""

import json
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from crewai_productfeature_planner.apis import app


@pytest.fixture(autouse=True)
def _clean_oauth_env(monkeypatch):
    for key in (
        "SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET",
        "SLACK_ACCESS_TOKEN", "SLACK_REFRESH_TOKEN",
        "SLACK_SIGNING_SECRET", "SLACK_VERIFICATION_TOKEN",
        "SLACK_BYPASS",
    ):
        monkeypatch.delenv(key, raising=False)


async def _get_callback(params: str = ""):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        return await ac.get(f"/slack/oauth/callback?{params}")


# ---- error param from Slack ----

@pytest.mark.asyncio
async def test_oauth_callback_error_param():
    resp = await _get_callback("error=access_denied")
    assert resp.status_code == 400
    assert "access_denied" in resp.text


# ---- missing code ----

@pytest.mark.asyncio
async def test_oauth_callback_missing_code():
    resp = await _get_callback("")
    assert resp.status_code == 400
    assert "Missing" in resp.text or "code" in resp.text.lower()


# ---- missing client credentials ----

@pytest.mark.asyncio
async def test_oauth_callback_no_client_creds():
    resp = await _get_callback("code=test_code")
    assert resp.status_code == 400
    assert "CLIENT_ID" in resp.text or "failed" in resp.text.lower()


# ---- successful code exchange ----

@pytest.mark.asyncio
async def test_oauth_callback_success(monkeypatch):
    monkeypatch.setenv("SLACK_CLIENT_ID", "cid123")
    monkeypatch.setenv("SLACK_CLIENT_SECRET", "csec456")

    mock_result = {
        "ok": True,
        "access_token": "xoxb-test-token",
        "refresh_token": "xoxr-test-refresh",
        "expires_in": 43200,
        "team": {"name": "Test Team", "id": "T123"},
        "scope": "chat:write,channels:read",
        "bot_user_id": "BBOT",
        "app_id": "A123",
        "token_type": "bot",
    }

    with patch(
        "crewai_productfeature_planner.apis.slack.oauth_router._exchange_code",
        return_value=mock_result,
    ), patch(
        "crewai_productfeature_planner.apis.slack.oauth_router._apply_tokens",
        return_value={
            "team": "Test Team",
            "scope": "chat:write,channels:read",
            "bot_user_id": "BBOT",
            "bot_token_type": "static",
        },
    ):
        resp = await _get_callback("code=valid_code")

    assert resp.status_code == 200
    assert "Installed Successfully" in resp.text
    assert "Test Team" in resp.text


# ---- _exchange_code raises → 400 ----

@pytest.mark.asyncio
async def test_oauth_callback_exchange_failure(monkeypatch):
    monkeypatch.setenv("SLACK_CLIENT_ID", "cid")
    monkeypatch.setenv("SLACK_CLIENT_SECRET", "csec")

    with patch(
        "crewai_productfeature_planner.apis.slack.oauth_router._exchange_code",
        side_effect=RuntimeError("oauth.v2.access failed: invalid_code"),
    ):
        resp = await _get_callback("code=bad_code")

    assert resp.status_code == 400
    assert "Exchange Failed" in resp.text or "failed" in resp.text.lower()


# ---- _apply_tokens persists env ----

def test_apply_tokens_sets_env(monkeypatch, tmp_path):
    from crewai_productfeature_planner.apis.slack.oauth_router import _apply_tokens

    monkeypatch.delenv("SLACK_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_REFRESH_TOKEN", raising=False)

    # Prevent token manager persistence from failing
    with patch(
        "crewai_productfeature_planner.apis.slack.oauth_router._update_env_file",
    ), patch(
        "crewai_productfeature_planner.tools.slack_token_manager._persist_tokens",
    ), patch(
        "crewai_productfeature_planner.tools.slack_token_manager._set_token_env",
    ):
        summary = _apply_tokens({
            "access_token": "xoxb-new-token",
            "refresh_token": "xoxr-new-refresh",
            "expires_in": 43200,
            "team": {"name": "T", "id": "TID"},
            "scope": "chat:write",
            "bot_user_id": "B1",
            "app_id": "A1",
            "token_type": "bot",
        })

    import os
    assert os.environ.get("SLACK_ACCESS_TOKEN") == "xoxb-new-token"
    assert summary["team"] == "T"
    assert summary["bot_user_id"] == "B1"
