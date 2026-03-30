"""Tests for the background Slack token refresh scheduler."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

MOD = "crewai_productfeature_planner.tools.token_refresh_scheduler"


@pytest.fixture(autouse=True)
def _reset_scheduler():
    """Ensure no scheduler thread leaks between tests."""
    import crewai_productfeature_planner.tools.token_refresh_scheduler as sched

    yield
    sched._stop_event.set()
    if sched._scheduler_thread and sched._scheduler_thread.is_alive():
        sched._scheduler_thread.join(timeout=5)
    sched._scheduler_thread = None
    sched._stop_event.clear()


class TestStartStop:
    """Start / stop lifecycle."""

    def test_start_returns_false_without_credentials(self, monkeypatch):
        monkeypatch.delenv("SLACK_CLIENT_ID", raising=False)
        monkeypatch.delenv("SLACK_CLIENT_SECRET", raising=False)

        from crewai_productfeature_planner.tools.token_refresh_scheduler import (
            start_token_refresh_scheduler,
        )

        assert start_token_refresh_scheduler() is False

    def test_start_returns_false_when_disabled(self, monkeypatch):
        monkeypatch.setenv("SLACK_CLIENT_ID", "cid")
        monkeypatch.setenv("SLACK_CLIENT_SECRET", "csec")
        monkeypatch.setenv("TOKEN_REFRESH_SCHEDULER_ENABLED", "false")

        from crewai_productfeature_planner.tools.token_refresh_scheduler import (
            start_token_refresh_scheduler,
        )

        assert start_token_refresh_scheduler() is False

    def test_start_and_stop(self, monkeypatch):
        monkeypatch.setenv("SLACK_CLIENT_ID", "cid")
        monkeypatch.setenv("SLACK_CLIENT_SECRET", "csec")
        monkeypatch.setenv("TOKEN_REFRESH_INTERVAL_SECONDS", "3600")

        # Prevent actual refresh logic from running
        with patch(f"{MOD}._refresh_expiring_tokens", return_value=0):
            from crewai_productfeature_planner.tools.token_refresh_scheduler import (
                start_token_refresh_scheduler,
                stop_token_refresh_scheduler,
            )

            assert start_token_refresh_scheduler() is True
            # Second start returns False (already running)
            assert start_token_refresh_scheduler() is False
            stop_token_refresh_scheduler()

    def test_get_scheduler_status(self, monkeypatch):
        from crewai_productfeature_planner.tools.token_refresh_scheduler import (
            get_scheduler_status,
        )

        status = get_scheduler_status()
        assert "running" in status
        assert "interval_seconds" in status
        assert "buffer_seconds" in status


class TestRefreshLogic:
    """Unit tests for _refresh_expiring_tokens."""

    def test_no_teams_returns_zero(self):
        from crewai_productfeature_planner.tools.token_refresh_scheduler import (
            _refresh_expiring_tokens,
        )

        REPO = "crewai_productfeature_planner.mongodb.slack_oauth.repository"
        with patch(f"{REPO}.get_all_teams", return_value=[]):
            assert _refresh_expiring_tokens() == 0

    def test_static_token_skipped(self):
        """Static (xoxb-) tokens without refresh_token are never refreshed."""
        from crewai_productfeature_planner.tools.token_refresh_scheduler import (
            _refresh_expiring_tokens,
        )

        REPO = "crewai_productfeature_planner.mongodb.slack_oauth.repository"
        team = {
            "team_id": "T1",
            "access_token": "xoxb-static",
            "refresh_token": None,
            "expires_at": time.time() - 999,  # "expired" but static
        }
        with patch(f"{REPO}.get_all_teams", return_value=[team]):
            assert _refresh_expiring_tokens() == 0

    def test_valid_token_not_refreshed(self):
        """Token with plenty of time left is not refreshed."""
        from crewai_productfeature_planner.tools.token_refresh_scheduler import (
            _refresh_expiring_tokens,
        )

        REPO = "crewai_productfeature_planner.mongodb.slack_oauth.repository"
        TM = "crewai_productfeature_planner.tools.slack_token_manager"
        team = {
            "team_id": "T1",
            "access_token": "xoxe.xoxb-good",
            "refresh_token": "xoxr-good",
            "expires_at": time.time() + 7200,  # 2h remaining > 1h buffer
        }
        with patch(f"{REPO}.get_all_teams", return_value=[team]), \
             patch(f"{TM}.get_valid_token") as mock_gvt:
            assert _refresh_expiring_tokens() == 0
            mock_gvt.assert_not_called()

    def test_expiring_token_refreshed(self):
        """Token within buffer window triggers get_valid_token."""
        from crewai_productfeature_planner.tools.token_refresh_scheduler import (
            _refresh_expiring_tokens,
        )

        REPO = "crewai_productfeature_planner.mongodb.slack_oauth.repository"
        TM = "crewai_productfeature_planner.tools.slack_token_manager"
        team = {
            "team_id": "T1",
            "access_token": "xoxe.xoxb-expiring",
            "refresh_token": "xoxr-valid",
            "expires_at": time.time() + 600,  # 10m remaining < 1h buffer
        }
        with patch(f"{REPO}.get_all_teams", return_value=[team]), \
             patch(f"{TM}.get_valid_token", return_value="xoxe.xoxb-new"):
            assert _refresh_expiring_tokens() == 1

    def test_expired_token_triggers_refresh(self):
        """Already-expired token triggers get_valid_token."""
        from crewai_productfeature_planner.tools.token_refresh_scheduler import (
            _refresh_expiring_tokens,
        )

        REPO = "crewai_productfeature_planner.mongodb.slack_oauth.repository"
        TM = "crewai_productfeature_planner.tools.slack_token_manager"
        team = {
            "team_id": "T1",
            "access_token": "xoxe.xoxb-dead",
            "refresh_token": "xoxr-stale",
            "expires_at": time.time() - 3600,  # expired 1h ago
        }
        with patch(f"{REPO}.get_all_teams", return_value=[team]), \
             patch(f"{TM}.get_valid_token", return_value="xoxe.xoxb-new"):
            assert _refresh_expiring_tokens() == 1

    def test_failed_refresh_counted_as_zero(self):
        """When get_valid_token returns None, it's not counted as refreshed."""
        from crewai_productfeature_planner.tools.token_refresh_scheduler import (
            _refresh_expiring_tokens,
        )

        REPO = "crewai_productfeature_planner.mongodb.slack_oauth.repository"
        TM = "crewai_productfeature_planner.tools.slack_token_manager"
        team = {
            "team_id": "T1",
            "access_token": "xoxe.xoxb-dead",
            "refresh_token": "xoxr-invalid",
            "expires_at": time.time() - 3600,
        }
        with patch(f"{REPO}.get_all_teams", return_value=[team]), \
             patch(f"{TM}.get_valid_token", return_value=None):
            assert _refresh_expiring_tokens() == 0

    def test_multiple_teams(self):
        """Two teams: one needs refresh, one doesn't."""
        from crewai_productfeature_planner.tools.token_refresh_scheduler import (
            _refresh_expiring_tokens,
        )

        REPO = "crewai_productfeature_planner.mongodb.slack_oauth.repository"
        TM = "crewai_productfeature_planner.tools.slack_token_manager"
        teams = [
            {
                "team_id": "T_OK",
                "access_token": "xoxe.xoxb-ok",
                "refresh_token": "xoxr-ok",
                "expires_at": time.time() + 7200,  # plenty of time
            },
            {
                "team_id": "T_EXPIRING",
                "access_token": "xoxe.xoxb-expiring",
                "refresh_token": "xoxr-expiring",
                "expires_at": time.time() + 300,  # 5min < 1h buffer
            },
        ]
        with patch(f"{REPO}.get_all_teams", return_value=teams), \
             patch(f"{TM}.get_valid_token", return_value="xoxe.xoxb-new") as mock_gvt:
            assert _refresh_expiring_tokens() == 1
            mock_gvt.assert_called_once_with("T_EXPIRING")


class TestLifecycleIntegration:
    """Verify the scheduler is wired into server startup/shutdown."""

    def test_scheduler_started_in_lifespan(self):
        """The _lifespan function should call start_token_refresh_scheduler."""
        import importlib
        import crewai_productfeature_planner.apis as apis_mod

        source = importlib.util.find_spec(apis_mod.__name__).origin
        with open(source) as f:
            content = f.read()

        assert "start_token_refresh_scheduler" in content
        assert "stop_token_refresh_scheduler" in content
