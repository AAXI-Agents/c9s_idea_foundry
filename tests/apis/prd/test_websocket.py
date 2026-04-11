"""Tests for WS /flow/runs/{run_id}/ws WebSocket endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app
from crewai_productfeature_planner.apis.shared import FlowRun, FlowStatus, runs


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


@pytest.fixture(autouse=True)
def _clear_runs():
    runs.clear()
    yield
    runs.clear()


# Disable the background poll loop for all WebSocket tests —
# it interferes with the synchronous TestClient.

import crewai_productfeature_planner.apis.prd._route_websocket as _ws_mod


@pytest.fixture(autouse=True)
def _disable_poll_loop():
    """Disable WS poll loop for tests."""
    _ws_mod._enable_poll_loop = False
    yield
    _ws_mod._enable_poll_loop = True


# ── Tests ─────────────────────────────────────────────────────


class TestWebSocketEndpoint:
    """Tests for WS /flow/runs/{run_id}/ws."""

    def test_connect_and_receive_initial_status(self, client):
        """WebSocket should send initial status snapshot on connect."""
        run = FlowRun(run_id="ws-1", flow_name="prd")
        run.status = FlowStatus.RUNNING
        runs["ws-1"] = run

        with client.websocket_connect("/flow/runs/ws-1/ws") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "status_update"
            assert msg["run_id"] == "ws-1"
            assert msg["status"] == "running"

    def test_connect_run_not_found(self, client):
        """WebSocket should send error when run_id does not exist."""
        with (
            patch(
                "crewai_productfeature_planner.mongodb.crew_jobs.find_job",
                return_value=None,
            ),
            client.websocket_connect("/flow/runs/missing/ws") as ws,
        ):
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "not found" in msg["message"]

    def test_ping_pong(self, client):
        """Client sending ping should receive pong."""
        run = FlowRun(run_id="ws-2", flow_name="prd")
        run.status = FlowStatus.COMPLETED
        runs["ws-2"] = run

        with client.websocket_connect("/flow/runs/ws-2/ws") as ws:
            # consume initial status
            ws.receive_json()
            ws.send_json({"type": "ping"})
            msg = ws.receive_json()
            assert msg["type"] == "pong"

    def test_get_status_command(self, client):
        """Client requesting get_status should receive fresh snapshot."""
        run = FlowRun(run_id="ws-3", flow_name="prd")
        run.status = FlowStatus.RUNNING
        runs["ws-3"] = run

        with client.websocket_connect("/flow/runs/ws-3/ws") as ws:
            # consume initial
            ws.receive_json()
            ws.send_json({"type": "get_status"})
            msg = ws.receive_json()
            assert msg["type"] == "status_update"
            assert msg["run_id"] == "ws-3"

    def test_unknown_message_type(self, client):
        """Unknown message type should return error."""
        run = FlowRun(run_id="ws-4", flow_name="prd")
        run.status = FlowStatus.COMPLETED
        runs["ws-4"] = run

        with client.websocket_connect("/flow/runs/ws-4/ws") as ws:
            ws.receive_json()
            ws.send_json({"type": "bogus"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "Unknown" in msg["message"]

    def test_invalid_json(self, client):
        """Non-JSON text should return error."""
        run = FlowRun(run_id="ws-5", flow_name="prd")
        run.status = FlowStatus.COMPLETED
        runs["ws-5"] = run

        with client.websocket_connect("/flow/runs/ws-5/ws") as ws:
            ws.receive_json()
            ws.send_text("not json")
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "Invalid JSON" in msg["message"]

    def test_initial_snapshot_with_db_fallback(self, client):
        """When run not in memory, should fall back to MongoDB job."""
        job_doc = {
            "job_id": "ws-db",
            "status": "completed",
            "error": None,
        }
        with (
            patch(
                "crewai_productfeature_planner.mongodb.crew_jobs.find_job",
                return_value=job_doc,
            ),
            client.websocket_connect("/flow/runs/ws-db/ws") as ws,
        ):
            msg = ws.receive_json()
            assert msg["type"] == "status_update"
            assert msg["status"] == "completed"

    def test_status_includes_sections(self, client):
        """Status snapshot should include section progress."""
        run = FlowRun(run_id="ws-6", flow_name="prd")
        run.status = FlowStatus.RUNNING
        run.active_agents = ["openai"]
        runs["ws-6"] = run

        with client.websocket_connect("/flow/runs/ws-6/ws") as ws:
            msg = ws.receive_json()
            assert "sections_approved" in msg
            assert "sections_total" in msg
            assert msg["active_agents"] == ["openai"]


class TestBroadcastSync:
    """Tests for the broadcast_sync helper."""

    def test_broadcast_sync_no_loop(self):
        """broadcast_sync should not raise when no event loop is running."""
        from crewai_productfeature_planner.apis.prd._route_websocket import (
            broadcast_sync,
        )
        # Should not raise
        broadcast_sync("nonexistent", {"type": "test"})

    def test_interaction_to_event(self):
        """Interaction doc should be converted to agent_activity event."""
        from crewai_productfeature_planner.apis.prd._route_websocket import (
            _interaction_to_event,
        )
        from datetime import datetime, timezone

        doc = {
            "interaction_id": "abc",
            "source": "slack",
            "intent": "create_prd",
            "agent_response": "I'll create a PRD",
            "run_id": "r-1",
            "user_id": "u-1",
            "created_at": datetime(2026, 4, 10, tzinfo=timezone.utc),
            "predicted_next_step": {"next_step": "approve"},
        }
        event = _interaction_to_event(doc)
        assert event["type"] == "agent_activity"
        assert event["interaction_id"] == "abc"
        assert event["source"] == "slack"
        assert event["run_id"] == "r-1"
        assert "2026-04-10" in event["created_at"]
