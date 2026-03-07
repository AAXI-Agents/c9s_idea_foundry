"""Tests for the Slack token rotation manager (team-scoped, MongoDB-backed)."""

import time
from unittest.mock import patch

import pytest

import crewai_productfeature_planner.tools.slack_token_manager as tm

# Module path for patching shortcuts
_REPO = "crewai_productfeature_planner.mongodb.slack_oauth.repository"

TEAM_A = "T_TEAM_A"
TEAM_B = "T_TEAM_B"


@pytest.fixture(autouse=True)
def _reset_token_state(monkeypatch):
    """Clear the per-team in-memory cache and client-credential env vars."""
    monkeypatch.delenv("SLACK_CLIENT_ID", raising=False)
    monkeypatch.delenv("SLACK_CLIENT_SECRET", raising=False)
    tm._cache.clear()


# ---- helpers ----

def _fake_team_doc(
    team_id: str = TEAM_A,
    access_token: str = "xoxb-abc",
    refresh_token: str | None = "xoxr-abc",
    expires_at: float | None = None,
) -> dict:
    """Return a minimal MongoDB slackOAuth document."""
    return {
        "team_id": team_id,
        "team_name": "Acme",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at or time.time() + 7200,
        "installed_at": time.time(),
        "updated_at": time.time(),
    }


# ---------------------------------------------------------------------------
# get_valid_token
# ---------------------------------------------------------------------------

class TestGetValidToken:
    def test_returns_none_when_no_teams_installed(self):
        with patch(f"{_REPO}.get_all_teams", return_value=[]):
            token = tm.get_valid_token()
        assert token is None

    def test_auto_resolves_single_team(self):
        doc = _fake_team_doc()
        with patch(f"{_REPO}.get_all_teams", return_value=[doc]), \
             patch(f"{_REPO}.get_team", return_value=doc):
            token = tm.get_valid_token()
        assert token == "xoxb-abc"

    def test_returns_none_when_multiple_teams_no_id(self):
        docs = [_fake_team_doc(TEAM_A), _fake_team_doc(TEAM_B)]
        with patch(f"{_REPO}.get_all_teams", return_value=docs):
            token = tm.get_valid_token()
        assert token is None

    def test_loads_valid_token_from_mongodb(self):
        doc = _fake_team_doc(expires_at=time.time() + 7200)
        with patch(f"{_REPO}.get_team", return_value=doc), \
             patch(f"{_REPO}.get_all_teams"):
            token = tm.get_valid_token(TEAM_A)
        assert token == "xoxb-abc"
        # Also cached
        assert tm._cache[TEAM_A]["access_token"] == "xoxb-abc"

    def test_returns_cached_token_on_second_call(self):
        doc = _fake_team_doc()
        with patch(f"{_REPO}.get_team", return_value=doc), \
             patch(f"{_REPO}.get_all_teams"):
            t1 = tm.get_valid_token(TEAM_A)
        # Second call should hit cache — no MongoDB patch needed
        t2 = tm.get_valid_token(TEAM_A)
        assert t1 == t2 == "xoxb-abc"

    def test_refreshes_expired_token(self, monkeypatch):
        monkeypatch.setenv("SLACK_CLIENT_ID", "cid")
        monkeypatch.setenv("SLACK_CLIENT_SECRET", "csec")

        doc = _fake_team_doc(
            access_token="xoxe.xoxb-old",
            refresh_token="xoxr-old",
            expires_at=time.time() - 100,  # expired
        )
        mock_refresh = {
            "ok": True,
            "access_token": "xoxe.xoxb-refreshed",
            "refresh_token": "xoxr-new",
            "expires_in": 43200,
        }

        with patch(f"{_REPO}.get_team", return_value=doc), \
             patch(f"{_REPO}.get_all_teams"), \
             patch(f"{_REPO}.update_tokens") as mock_update, \
             patch.object(tm, "_do_refresh", return_value=mock_refresh):
            token = tm.get_valid_token(TEAM_A)

        assert token == "xoxe.xoxb-refreshed"
        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args.kwargs
        assert call_kwargs["team_id"] == TEAM_A
        assert call_kwargs["access_token"] == "xoxe.xoxb-refreshed"
        assert call_kwargs["refresh_token"] == "xoxr-new"

    def test_falls_back_to_expired_token_on_refresh_failure(self, monkeypatch):
        monkeypatch.setenv("SLACK_CLIENT_ID", "cid")
        monkeypatch.setenv("SLACK_CLIENT_SECRET", "csec")

        doc = _fake_team_doc(
            access_token="xoxb-fallback",
            refresh_token="xoxr-bad",
            expires_at=time.time() - 100,
        )

        with patch(f"{_REPO}.get_team", return_value=doc), \
             patch(f"{_REPO}.get_all_teams"), \
             patch.object(tm, "_do_refresh", side_effect=RuntimeError("bad")):
            token = tm.get_valid_token(TEAM_A)

        assert token == "xoxb-fallback"

    def test_returns_none_for_unknown_team(self):
        with patch(f"{_REPO}.get_team", return_value=None), \
             patch(f"{_REPO}.get_all_teams"):
            token = tm.get_valid_token("T_UNKNOWN")
        assert token is None

    def test_no_refresh_when_rotation_not_configured(self):
        """Without SLACK_CLIENT_ID/SECRET, no refresh attempt is made."""
        doc = _fake_team_doc(expires_at=time.time() - 100)

        with patch(f"{_REPO}.get_team", return_value=doc), \
             patch(f"{_REPO}.get_all_teams"), \
             patch.object(tm, "_do_refresh") as mock_refresh:
            token = tm.get_valid_token(TEAM_A)

        mock_refresh.assert_not_called()
        # Returns the expired token as a last resort
        assert token == "xoxb-abc"

    def test_static_token_cached_with_long_ttl(self):
        """Static (non-rotating) tokens with no refresh_token bypass expiry checks."""
        doc = _fake_team_doc(
            access_token="xoxb-static",
            refresh_token=None,
            expires_at=time.time() - 1000,  # expired long ago
        )
        with patch(f"{_REPO}.get_team", return_value=doc) as mock_get, \
             patch(f"{_REPO}.get_all_teams"):
            t1 = tm.get_valid_token(TEAM_A)

        assert t1 == "xoxb-static"
        # Token should be cached with a long TTL (24h)
        cached = tm._cache_entry(TEAM_A)
        assert cached is not None
        assert cached["expires_at"] > time.time() + 80000  # ~24 h

        # Second call should hit cache — no MongoDB round-trip
        mock_get.reset_mock()
        t2 = tm.get_valid_token(TEAM_A)
        assert t2 == "xoxb-static"
        mock_get.assert_not_called()

    def test_fallback_cache_ttl_survives_buffer_subtraction(self):
        """Fallback short-TTL cache entry should survive _needs_refresh check."""
        # Setup: rotating token that can't be refreshed (no client creds)
        doc = _fake_team_doc(
            access_token="xoxe.xoxb-expired",
            refresh_token="xoxr-tok",
            expires_at=time.time() - 100,
        )
        with patch(f"{_REPO}.get_team", return_value=doc), \
             patch(f"{_REPO}.get_all_teams"):
            t1 = tm.get_valid_token(TEAM_A)

        assert t1 == "xoxe.xoxb-expired"
        # The cached entry should NOT be immediately stale
        cached = tm._cache_entry(TEAM_A)
        assert cached is not None
        assert not tm._needs_refresh(cached), (
            "Fallback cache entry should survive at least one "
            "_needs_refresh check (TTL must account for buffer)"
        )


# ---------------------------------------------------------------------------
# invalidate
# ---------------------------------------------------------------------------

class TestInvalidate:
    def test_invalidate_single_team(self):
        tm._cache[TEAM_A] = {"access_token": "x"}
        tm._cache[TEAM_B] = {"access_token": "y"}
        tm.invalidate(TEAM_A)
        assert TEAM_A not in tm._cache
        assert TEAM_B in tm._cache

    def test_invalidate_all(self):
        tm._cache[TEAM_A] = {"access_token": "x"}
        tm._cache[TEAM_B] = {"access_token": "y"}
        tm.invalidate()
        assert tm._cache == {}

    def test_invalidate_nonexistent_team_is_noop(self):
        tm.invalidate("T_NONEXISTENT")  # Should not raise


# ---------------------------------------------------------------------------
# exchange_token
# ---------------------------------------------------------------------------

class TestExchangeToken:
    def test_exchange_raises_without_creds(self):
        with pytest.raises(ValueError, match="SLACK_CLIENT_ID"):
            tm.exchange_token(TEAM_A, token="xoxb-old")

    def test_exchange_raises_without_token(self, monkeypatch):
        monkeypatch.setenv("SLACK_CLIENT_ID", "cid")
        monkeypatch.setenv("SLACK_CLIENT_SECRET", "csec")
        with pytest.raises(ValueError, match="token"):
            tm.exchange_token(TEAM_A)

    def test_exchange_success(self, monkeypatch):
        monkeypatch.setenv("SLACK_CLIENT_ID", "cid")
        monkeypatch.setenv("SLACK_CLIENT_SECRET", "csec")

        mock_result = {
            "ok": True,
            "access_token": "xoxe.xoxb-exchanged",
            "refresh_token": "xoxr-exchanged",
            "expires_in": 43200,
        }

        with patch.object(tm, "_post_slack", return_value=mock_result), \
             patch(f"{_REPO}.update_tokens") as mock_update:
            result = tm.exchange_token(TEAM_A, token="xoxb-old")

        assert result["access_token"] == "xoxe.xoxb-exchanged"
        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args.kwargs
        assert call_kwargs["team_id"] == TEAM_A
        assert call_kwargs["access_token"] == "xoxe.xoxb-exchanged"
        # Cache should be updated
        assert tm._cache[TEAM_A]["access_token"] == "xoxe.xoxb-exchanged"


# ---------------------------------------------------------------------------
# token_status (delegates to MongoDB repo)
# ---------------------------------------------------------------------------

class TestTokenStatus:
    def test_delegates_to_repo(self):
        expected = {"has_token": True, "team_id": TEAM_A}
        with patch(f"{_REPO}.token_status", return_value=expected) as mock_ts:
            status = tm.token_status(TEAM_A)
        mock_ts.assert_called_once_with(TEAM_A)
        assert status == expected


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
        assert tm._needs_refresh({}) is True
        assert tm._needs_refresh({"access_token": ""}) is True

    def test_needs_refresh_expired(self):
        entry = {"access_token": "xoxb-expired", "expires_at": time.time() - 100}
        assert tm._needs_refresh(entry) is True

    def test_no_refresh_needed(self):
        entry = {"access_token": "xoxb-valid", "expires_at": time.time() + 3600}
        assert tm._needs_refresh(entry) is False

    def test_refresh_within_buffer(self):
        entry = {"access_token": "xoxb-soon", "expires_at": time.time() + 200}
        assert tm._needs_refresh(entry) is True


# ---------------------------------------------------------------------------
# _basic_auth_header
# ---------------------------------------------------------------------------

class TestBasicAuthHeader:
    def test_encodes_correctly(self):
        import base64
        hdr = tm._basic_auth_header("client_id", "client_secret")
        expected = base64.b64encode(b"client_id:client_secret").decode()
        assert hdr == f"Basic {expected}"


# ---------------------------------------------------------------------------
# _cache_entry / _set_cache
# ---------------------------------------------------------------------------

class TestCacheHelpers:
    def test_set_and_get(self):
        tm._set_cache(TEAM_A, "xoxb-cached", "xoxr-cached", time.time() + 3600)
        entry = tm._cache_entry(TEAM_A)
        assert entry is not None
        assert entry["access_token"] == "xoxb-cached"
        assert entry["refresh_token"] == "xoxr-cached"
        assert "last_refresh_at" in entry

    def test_cache_entry_returns_none_for_unknown(self):
        assert tm._cache_entry("T_UNKNOWN") is None
