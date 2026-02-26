"""Tests for the Slack token rotation manager."""

import json
import os
import time
from unittest.mock import MagicMock, patch

import pytest

import crewai_productfeature_planner.tools.slack_token_manager as tm


@pytest.fixture(autouse=True)
def _reset_token_state(monkeypatch, tmp_path):
    """Reset module-level singleton and point token store to tmp."""
    monkeypatch.delenv("SLACK_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_CLIENT_ID", raising=False)
    monkeypatch.delenv("SLACK_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("SLACK_TOKEN_STORE", raising=False)

    # Point persistence to a temp file
    store_path = str(tmp_path / ".slack_tokens.json")
    monkeypatch.setenv("SLACK_TOKEN_STORE", store_path)

    # Clear module state
    tm.invalidate()


# ---------------------------------------------------------------------------
# get_valid_token
# ---------------------------------------------------------------------------

class TestGetValidToken:
    def test_returns_none_when_nothing_configured(self):
        token = tm.get_valid_token()
        assert token is None

    def test_returns_static_env_token(self, monkeypatch):
        monkeypatch.setenv("SLACK_ACCESS_TOKEN", "xoxb-static-token")
        token = tm.get_valid_token()
        assert token == "xoxb-static-token"

    def test_caches_token_on_second_call(self, monkeypatch):
        monkeypatch.setenv("SLACK_ACCESS_TOKEN", "xoxb-cached")
        t1 = tm.get_valid_token()
        t2 = tm.get_valid_token()
        assert t1 == t2 == "xoxb-cached"

    def test_loads_persisted_tokens(self, monkeypatch):
        store = tm._token_store_path()
        payload = {
            "access_token": "xoxe.xoxb-persisted",
            "refresh_token": "xoxr-refresh",
            "expires_at": time.time() + 3600,
            "last_refresh_at": time.time(),
        }
        with open(store, "w") as fh:
            json.dump(payload, fh)

        token = tm.get_valid_token()
        assert token == "xoxe.xoxb-persisted"

    def test_refreshes_expired_token(self, monkeypatch):
        monkeypatch.setenv("SLACK_CLIENT_ID", "cid")
        monkeypatch.setenv("SLACK_CLIENT_SECRET", "csec")
        monkeypatch.setenv("SLACK_REFRESH_TOKEN", "xoxr-refresh")

        mock_result = {
            "ok": True,
            "access_token": "xoxe.xoxb-refreshed",
            "refresh_token": "xoxr-new-refresh",
            "expires_in": 43200,
        }

        with patch.object(tm, "_do_refresh", return_value=mock_result):
            token = tm.get_valid_token()
        assert token == "xoxe.xoxb-refreshed"

    def test_falls_back_to_static_on_refresh_failure(self, monkeypatch):
        monkeypatch.setenv("SLACK_CLIENT_ID", "cid")
        monkeypatch.setenv("SLACK_CLIENT_SECRET", "csec")
        monkeypatch.setenv("SLACK_REFRESH_TOKEN", "xoxr-bad")
        monkeypatch.setenv("SLACK_ACCESS_TOKEN", "xoxb-fallback")

        with patch.object(tm, "_do_refresh", side_effect=RuntimeError("invalid_refresh_token")):
            token = tm.get_valid_token()
        assert token == "xoxb-fallback"


# ---------------------------------------------------------------------------
# invalidate
# ---------------------------------------------------------------------------

class TestInvalidate:
    def test_invalidate_clears_cache(self, monkeypatch):
        monkeypatch.setenv("SLACK_ACCESS_TOKEN", "xoxb-test")
        tm.get_valid_token()

        tm.invalidate()

        # Access internal state directly
        assert tm._access_token is None
        assert tm._expires_at == 0.0


# ---------------------------------------------------------------------------
# exchange_token
# ---------------------------------------------------------------------------

class TestExchangeToken:
    def test_exchange_raises_without_creds(self):
        with pytest.raises(ValueError, match="SLACK_CLIENT_ID"):
            tm.exchange_token()

    def test_exchange_success(self, monkeypatch):
        monkeypatch.setenv("SLACK_CLIENT_ID", "cid")
        monkeypatch.setenv("SLACK_CLIENT_SECRET", "csec")
        monkeypatch.setenv("SLACK_ACCESS_TOKEN", "xoxb-old")

        mock_result = {
            "ok": True,
            "access_token": "xoxe.xoxb-new",
            "refresh_token": "xoxr-new",
            "expires_in": 43200,
        }

        with patch.object(tm, "_post_slack", return_value=mock_result):
            result = tm.exchange_token()

        assert result["access_token"] == "xoxe.xoxb-new"
        assert os.environ.get("SLACK_ACCESS_TOKEN") == "xoxe.xoxb-new"
        assert os.environ.get("SLACK_REFRESH_TOKEN") == "xoxr-new"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_persist_and_load(self):
        tm._persist_tokens("xoxb-p", "xoxr-p", time.time() + 3600)
        loaded = tm._load_persisted_tokens()
        assert loaded["access_token"] == "xoxb-p"
        assert loaded["refresh_token"] == "xoxr-p"

    def test_load_empty_when_no_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SLACK_TOKEN_STORE", str(tmp_path / "missing.json"))
        loaded = tm._load_persisted_tokens()
        assert loaded == {}


# ---------------------------------------------------------------------------
# token_status
# ---------------------------------------------------------------------------

class TestTokenStatus:
    def test_status_no_token(self):
        status = tm.token_status()
        assert status["has_token"] is False
        assert status["token_type"] == "none"

    def test_status_with_static_bot_token(self, monkeypatch):
        monkeypatch.setenv("SLACK_ACCESS_TOKEN", "xoxb-static")
        tm.get_valid_token()
        status = tm.token_status()
        assert status["has_token"] is True
        assert status["token_type"] == "static_bot"

    def test_status_rotating_token(self, monkeypatch):
        # Manually set module state to simulate a rotating token
        tm._access_token = "xoxe.xoxb-rotating"
        tm._expires_at = time.time() + 3600
        status = tm.token_status()
        assert status["is_rotating"] is True
        assert status["token_type"] == "rotating_bot"


# ---------------------------------------------------------------------------
# _is_rotating_token
# ---------------------------------------------------------------------------

class TestIsRotatingToken:
    def test_rotating(self):
        assert tm._is_rotating_token("xoxe.xoxb-123") is True
        assert tm._is_rotating_token("xoxe.xoxp-456") is True

    def test_static(self):
        assert tm._is_rotating_token("xoxb-123") is False
        assert tm._is_rotating_token("xoxp-456") is False


# ---------------------------------------------------------------------------
# _needs_refresh
# ---------------------------------------------------------------------------

class TestNeedsRefresh:
    def test_needs_refresh_no_token(self):
        assert tm._needs_refresh() is True

    def test_needs_refresh_expired(self):
        tm._access_token = "xoxb-expired"
        tm._expires_at = time.time() - 100
        assert tm._needs_refresh() is True

    def test_no_refresh_needed(self):
        tm._access_token = "xoxb-valid"
        tm._expires_at = time.time() + 3600
        assert tm._needs_refresh() is False

    def test_refresh_within_buffer(self):
        tm._access_token = "xoxb-soon"
        tm._expires_at = time.time() + 200  # less than 300s buffer
        assert tm._needs_refresh() is True
