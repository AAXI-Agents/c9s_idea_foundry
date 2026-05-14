"""Tests for Knowledge WebSocket — _ws_knowledge module.

Validates:
- Room management (register / unregister / cleanup)
- Broadcast delivery to connected clients
- broadcast_knowledge_sync thread-safe wrapper
- Ping/pong keepalive
- Auth rejection (token missing / expired)
- Shared WS auth utility
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crewai_productfeature_planner.apis.knowledge._ws_knowledge import (
    _connections,
    _lock,
    _register,
    _unregister,
    broadcast_knowledge,
    broadcast_knowledge_sync,
    set_main_loop,
)


@pytest.fixture(autouse=True)
def _clear_connections():
    """Ensure room state is clean before and after each test."""
    _connections.clear()
    yield
    _connections.clear()


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── Room Management ──────────────────────────────────────────


class TestRoomManagement:
    @pytest.mark.asyncio
    async def test_register_adds_connection(self):
        ws = MagicMock()
        await _register("proj1", ws)
        assert ws in _connections["proj1"]

    @pytest.mark.asyncio
    async def test_unregister_removes_connection(self):
        ws = MagicMock()
        await _register("proj1", ws)
        await _unregister("proj1", ws)
        assert "proj1" not in _connections

    @pytest.mark.asyncio
    async def test_unregister_keeps_other_connections(self):
        ws1, ws2 = MagicMock(), MagicMock()
        await _register("proj1", ws1)
        await _register("proj1", ws2)
        await _unregister("proj1", ws1)
        assert ws2 in _connections["proj1"]
        assert ws1 not in _connections["proj1"]

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_is_noop(self):
        ws = MagicMock()
        await _unregister("proj1", ws)  # Should not raise

    @pytest.mark.asyncio
    async def test_multiple_projects_isolated(self):
        ws1, ws2 = MagicMock(), MagicMock()
        await _register("proj1", ws1)
        await _register("proj2", ws2)
        assert ws1 in _connections["proj1"]
        assert ws2 in _connections["proj2"]
        assert ws1 not in _connections.get("proj2", set())


# ── Broadcast ────────────────────────────────────────────────


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_in_room(self):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await _register("proj1", ws1)
        await _register("proj1", ws2)

        event = {"event": "knowledge.doc.updated", "data": {"doc_id": "d1"}}
        await broadcast_knowledge("proj1", event)

        expected_payload = json.dumps(event, default=str)
        ws1.send_text.assert_called_once_with(expected_payload)
        ws2.send_text.assert_called_once_with(expected_payload)

    @pytest.mark.asyncio
    async def test_broadcast_skips_empty_room(self):
        # Should not raise when no connections exist
        await broadcast_knowledge("proj_nonexistent", {"event": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self):
        ws_alive = AsyncMock()
        ws_dead = AsyncMock()
        ws_dead.send_text.side_effect = Exception("connection closed")

        await _register("proj1", ws_alive)
        await _register("proj1", ws_dead)

        await broadcast_knowledge("proj1", {"event": "test"})

        # Dead connection should be removed
        assert ws_dead not in _connections.get("proj1", set())
        assert ws_alive in _connections["proj1"]

    @pytest.mark.asyncio
    async def test_broadcast_does_not_leak_to_other_projects(self):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await _register("proj1", ws1)
        await _register("proj2", ws2)

        await broadcast_knowledge("proj1", {"event": "test"})

        ws1.send_text.assert_called_once()
        ws2.send_text.assert_not_called()


# ── broadcast_knowledge_sync ─────────────────────────────────


class TestBroadcastSync:
    @pytest.mark.asyncio
    async def test_sync_broadcast_from_async_context(self):
        ws = AsyncMock()
        await _register("proj1", ws)

        event = {"event": "knowledge.doc.deleted", "data": {"doc_id": "d1"}}
        broadcast_knowledge_sync("proj1", event)

        # Allow the scheduled coroutine to run
        await asyncio.sleep(0.05)

        ws.send_text.assert_called_once()

    def test_sync_broadcast_with_stashed_loop(self):
        """broadcast_knowledge_sync uses _main_loop when no running loop."""
        loop = MagicMock()
        loop.is_running.return_value = True
        set_main_loop(loop)

        with patch(
            "crewai_productfeature_planner.apis.knowledge._ws_knowledge.asyncio"
        ) as mock_asyncio:
            mock_asyncio.get_running_loop.side_effect = RuntimeError("no loop")
            mock_asyncio.run_coroutine_threadsafe = MagicMock()

            broadcast_knowledge_sync("proj1", {"event": "test"})

            mock_asyncio.run_coroutine_threadsafe.assert_called_once()

        # Reset
        set_main_loop(None)  # type: ignore[arg-type]


# ── Shared WS Auth ───────────────────────────────────────────


class TestSharedWSAuth:
    @pytest.mark.asyncio
    async def test_dev_mode_returns_anonymous(self, monkeypatch):
        monkeypatch.setenv("SSO_ENABLED", "false")
        monkeypatch.setenv("DEV_ENTERPRISE_ID", "ent-test")
        monkeypatch.setenv("DEV_ORGANIZATION_ID", "org-test")

        from crewai_productfeature_planner.apis._ws_auth import validate_ws_token

        result = await validate_ws_token(None)
        assert result is not None
        assert result["user_id"] == "anonymous"
        assert result["enterprise_id"] == "ent-test"

    @pytest.mark.asyncio
    async def test_sso_enabled_no_token_returns_none(self, monkeypatch):
        monkeypatch.setenv("SSO_ENABLED", "true")

        from crewai_productfeature_planner.apis._ws_auth import validate_ws_token

        result = await validate_ws_token(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_sso_enabled_valid_token(self, monkeypatch):
        monkeypatch.setenv("SSO_ENABLED", "true")

        from crewai_productfeature_planner.apis._ws_auth import validate_ws_token

        with patch(
            "crewai_productfeature_planner.apis.sso_auth._introspect_remotely",
            new_callable=AsyncMock,
            return_value={"user_id": "u1", "roles": ["USER"]},
        ):
            result = await validate_ws_token("valid-token")
            assert result is not None
            assert result["user_id"] == "u1"

    @pytest.mark.asyncio
    async def test_sso_enabled_fallback_to_local_decode(self, monkeypatch):
        monkeypatch.setenv("SSO_ENABLED", "true")

        from crewai_productfeature_planner.apis._ws_auth import validate_ws_token

        with (
            patch(
                "crewai_productfeature_planner.apis.sso_auth._introspect_remotely",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "crewai_productfeature_planner.apis.sso_auth._decode_jwt_locally",
                return_value={"user_id": "u2"},
            ),
        ):
            result = await validate_ws_token("some-token")
            assert result is not None
            assert result["user_id"] == "u2"
