"""Tests for session-scoped memory — DM vs channel context + admin gating."""

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.apis.slack.session_manager import (
    _active_sessions,
    _admin_cache,
    _channel_sessions,
    _lock,
    _pending_memory_entries,
    _pending_project_creates,
    activate_channel_project,
    can_manage_memory,
    deactivate_channel_session,
    ensure_channel_session_loaded,
    get_channel_project_id,
    get_channel_session,
    get_context_project_id,
    get_context_session,
    is_channel_admin,
    is_dm,
)

_SM = "crewai_productfeature_planner.apis.slack.session_manager"


@pytest.fixture(autouse=True)
def _clean_state():
    """Clear all module-level caches before each test."""
    _active_sessions.clear()
    _channel_sessions.clear()
    _pending_project_creates.clear()
    _pending_memory_entries.clear()
    _admin_cache.clear()
    yield
    _active_sessions.clear()
    _channel_sessions.clear()
    _pending_project_creates.clear()
    _pending_memory_entries.clear()
    _admin_cache.clear()


# ── is_dm ─────────────────────────────────────────────────────


class TestIsDm:
    def test_dm_channel(self):
        assert is_dm("D12345") is True

    def test_public_channel(self):
        assert is_dm("C12345") is False

    def test_group_dm(self):
        assert is_dm("G12345") is False

    def test_empty(self):
        assert is_dm("") is False


# ── is_channel_admin ──────────────────────────────────────────


class TestIsChannelAdmin:
    @patch(f"{_SM}._get_slack_client" if False else "crewai_productfeature_planner.tools.slack_tools._get_slack_client")
    def test_admin_true(self, mock_client_fn):
        client = MagicMock()
        client.users_info.return_value = {
            "ok": True,
            "user": {"is_admin": True, "is_owner": False},
        }
        mock_client_fn.return_value = client

        assert is_channel_admin("U1") is True
        # Second call should use cache
        assert is_channel_admin("U1") is True
        client.users_info.assert_called_once()

    @patch("crewai_productfeature_planner.tools.slack_tools._get_slack_client")
    def test_admin_false(self, mock_client_fn):
        client = MagicMock()
        client.users_info.return_value = {
            "ok": True,
            "user": {"is_admin": False, "is_owner": False},
        }
        mock_client_fn.return_value = client

        assert is_channel_admin("U2") is False

    @patch("crewai_productfeature_planner.tools.slack_tools._get_slack_client")
    def test_owner_is_admin(self, mock_client_fn):
        client = MagicMock()
        client.users_info.return_value = {
            "ok": True,
            "user": {"is_admin": False, "is_owner": True},
        }
        mock_client_fn.return_value = client

        assert is_channel_admin("U3") is True

    @patch("crewai_productfeature_planner.tools.slack_tools._get_slack_client")
    def test_no_client(self, mock_client_fn):
        mock_client_fn.return_value = None
        assert is_channel_admin("U4") is False

    @patch("crewai_productfeature_planner.tools.slack_tools._get_slack_client")
    def test_api_failure(self, mock_client_fn):
        client = MagicMock()
        client.users_info.side_effect = RuntimeError("API down")
        mock_client_fn.return_value = client

        assert is_channel_admin("U5") is False

    def test_cached_result(self):
        """Cached admin status is returned without Slack call."""
        _admin_cache["U6"] = True
        assert is_channel_admin("U6") is True


# ── can_manage_memory ─────────────────────────────────────────


class TestCanManageMemory:
    def test_dm_always_allowed(self):
        """Any user in a DM can manage memory."""
        assert can_manage_memory("U1", "D12345") is True

    @patch("crewai_productfeature_planner.tools.slack_tools._get_slack_client")
    def test_channel_admin_allowed(self, mock_client_fn):
        client = MagicMock()
        client.users_info.return_value = {
            "ok": True,
            "user": {"is_admin": True, "is_owner": False},
        }
        mock_client_fn.return_value = client

        assert can_manage_memory("U1", "C12345") is True

    @patch("crewai_productfeature_planner.tools.slack_tools._get_slack_client")
    def test_channel_non_admin_blocked(self, mock_client_fn):
        client = MagicMock()
        client.users_info.return_value = {
            "ok": True,
            "user": {"is_admin": False, "is_owner": False},
        }
        mock_client_fn.return_value = client

        assert can_manage_memory("U1", "C12345") is False


# ── Channel session management ────────────────────────────────


class TestChannelSessionManagement:

    @patch("crewai_productfeature_planner.mongodb.user_session.start_channel_session")
    def test_activate_channel_project_success(self, mock_start):
        mock_start.return_value = "chan-sid-1"

        result = activate_channel_project(
            channel_id="C1",
            project_id="p1",
            project_name="Channel Project",
            activated_by="U_ADMIN",
        )

        assert result == "chan-sid-1"
        assert "C1" in _channel_sessions
        sess = _channel_sessions["C1"]
        assert sess["project_id"] == "p1"
        assert sess["project_name"] == "Channel Project"
        assert sess["activated_by"] == "U_ADMIN"
        assert sess["active"] is True

    @patch("crewai_productfeature_planner.mongodb.user_session.start_channel_session")
    def test_activate_channel_project_failure(self, mock_start):
        mock_start.return_value = None

        result = activate_channel_project(
            channel_id="C2",
            project_id="p2",
            project_name="Fail",
            activated_by="U1",
        )

        assert result is None
        assert "C2" not in _channel_sessions

    @patch("crewai_productfeature_planner.mongodb.user_session.end_channel_session")
    def test_deactivate_channel_session(self, mock_end):
        mock_end.return_value = 1
        _channel_sessions["C1"] = {"project_id": "p1"}

        count = deactivate_channel_session("C1")

        assert count == 1
        assert "C1" not in _channel_sessions
        mock_end.assert_called_once_with(channel_id="C1")

    def test_get_channel_session_cached(self):
        _channel_sessions["C1"] = {"project_id": "p1", "active": True}
        assert get_channel_session("C1") == {"project_id": "p1", "active": True}

    def test_get_channel_session_empty(self):
        assert get_channel_session("C999") is None

    @patch("crewai_productfeature_planner.mongodb.user_session.get_active_channel_session")
    def test_ensure_channel_session_from_cache(self, mock_get):
        _channel_sessions["C1"] = {"project_id": "p1", "active": True}
        result = ensure_channel_session_loaded("C1")
        assert result == {"project_id": "p1", "active": True}
        mock_get.assert_not_called()

    @patch("crewai_productfeature_planner.mongodb.user_session.get_active_channel_session")
    def test_ensure_channel_session_from_db(self, mock_get):
        mock_get.return_value = {"project_id": "p2", "active": True}
        result = ensure_channel_session_loaded("C2")
        assert result["project_id"] == "p2"
        assert _channel_sessions["C2"]["project_id"] == "p2"

    @patch("crewai_productfeature_planner.mongodb.user_session.get_active_channel_session")
    def test_ensure_channel_session_none(self, mock_get):
        mock_get.return_value = None
        assert ensure_channel_session_loaded("C3") is None
        assert "C3" not in _channel_sessions

    @patch("crewai_productfeature_planner.mongodb.user_session.get_active_channel_session")
    def test_get_channel_project_id(self, mock_get):
        _channel_sessions["C1"] = {"project_id": "p1", "active": True}
        assert get_channel_project_id("C1") == "p1"
        mock_get.assert_not_called()

    @patch("crewai_productfeature_planner.mongodb.user_session.get_active_channel_session")
    def test_get_channel_project_id_none(self, mock_get):
        mock_get.return_value = None
        assert get_channel_project_id("C99") is None


# ── Context-aware dispatch ────────────────────────────────────


class TestContextDispatch:

    @patch("crewai_productfeature_planner.mongodb.user_session.get_active_session")
    def test_dm_uses_user_session(self, mock_get):
        _active_sessions["U1"] = {"project_id": "p_user", "active": True}
        result = get_context_session("U1", "D12345")
        assert result["project_id"] == "p_user"
        mock_get.assert_not_called()

    @patch("crewai_productfeature_planner.mongodb.user_session.get_active_channel_session")
    def test_channel_uses_channel_session(self, mock_get):
        _channel_sessions["C1"] = {"project_id": "p_chan", "active": True}
        result = get_context_session("U1", "C1")
        assert result["project_id"] == "p_chan"
        mock_get.assert_not_called()

    @patch("crewai_productfeature_planner.mongodb.user_session.get_active_session")
    def test_dm_project_id(self, mock_get):
        _active_sessions["U1"] = {"project_id": "p_dm", "active": True}
        assert get_context_project_id("U1", "D99") == "p_dm"

    @patch("crewai_productfeature_planner.mongodb.user_session.get_active_channel_session")
    def test_channel_project_id(self, mock_get):
        _channel_sessions["C5"] = {"project_id": "p_ch5", "active": True}
        assert get_context_project_id("U1", "C5") == "p_ch5"

    @patch("crewai_productfeature_planner.mongodb.user_session.get_active_channel_session")
    @patch("crewai_productfeature_planner.mongodb.user_session.get_active_session")
    def test_dm_and_channel_independent(self, mock_user_get, mock_chan_get):
        """DM and channel sessions are independent for the same user."""
        _active_sessions["U1"] = {"project_id": "p_dm", "active": True}
        _channel_sessions["C1"] = {"project_id": "p_chan", "active": True}

        assert get_context_project_id("U1", "D1") == "p_dm"
        assert get_context_project_id("U1", "C1") == "p_chan"
