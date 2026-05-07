"""Tests for GET /api/agentic-team/deliveries endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """Create a test client with agentic team enabled."""
    with patch.dict(
        "os.environ",
        {
            "AGENTIC_TEAM_ENABLED": "true",
            "AGENTIC_TEAM_WEBHOOK_SECRET": "test-secret",
            "WEBHOOK_DELIVERY_LOG_ENABLED": "true",
        },
    ):
        import importlib
        import crewai_productfeature_planner.apis.agentic_team._config as cfg

        importlib.reload(cfg)
        import crewai_productfeature_planner.apis.agentic_team._deliveries as dl

        importlib.reload(dl)

        from crewai_productfeature_planner.apis import app

        yield TestClient(app)


@pytest.fixture()
def disabled_client():
    """Create a test client with agentic team disabled."""
    with patch.dict(
        "os.environ",
        {"AGENTIC_TEAM_ENABLED": "false"},
    ):
        import importlib
        import crewai_productfeature_planner.apis.agentic_team._config as cfg

        importlib.reload(cfg)
        import crewai_productfeature_planner.apis.agentic_team._deliveries as dl

        importlib.reload(dl)

        from crewai_productfeature_planner.apis import app

        yield TestClient(app)


# ── GET /api/agentic-team/deliveries ──────────────────────────


class TestListDeliveries:
    """Test listing webhook deliveries."""

    @patch("crewai_productfeature_planner.apis.agentic_team._deliveries.list_deliveries")
    def test_returns_paginated_list(self, mock_list, client):
        mock_list.return_value = {
            "items": [
                {"delivery_id": "d1", "event": "task.completed"},
                {"delivery_id": "d2", "event": "task.failed"},
            ],
            "total": 2,
            "page": 1,
            "page_size": 50,
        }

        resp = client.get("/api/agentic-team/deliveries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @patch("crewai_productfeature_planner.apis.agentic_team._deliveries.list_deliveries")
    def test_passes_filters(self, mock_list, client):
        mock_list.return_value = {"items": [], "total": 0, "page": 1, "page_size": 50}

        client.get(
            "/api/agentic-team/deliveries",
            params={"event": "task.completed", "idea_id": "idea-1", "page": 2},
        )

        mock_list.assert_called_once()
        kwargs = mock_list.call_args[1]
        assert kwargs["event"] == "task.completed"
        assert kwargs["idea_id"] == "idea-1"
        assert kwargs["page"] == 2

    def test_disabled_returns_503(self, disabled_client):
        resp = disabled_client.get("/api/agentic-team/deliveries")
        assert resp.status_code == 503


# ── GET /api/agentic-team/deliveries/{delivery_id} ────────────


class TestGetDelivery:
    """Test getting a single delivery."""

    @patch("crewai_productfeature_planner.apis.agentic_team._deliveries.get_delivery")
    def test_returns_delivery(self, mock_get, client):
        mock_get.return_value = {
            "delivery_id": "del-001",
            "event": "task.completed",
            "payload": {"event": "task.completed"},
        }

        resp = client.get("/api/agentic-team/deliveries/del-001")
        assert resp.status_code == 200
        assert resp.json()["delivery_id"] == "del-001"

    @patch("crewai_productfeature_planner.apis.agentic_team._deliveries.get_delivery")
    def test_returns_404_when_not_found(self, mock_get, client):
        mock_get.return_value = None

        resp = client.get("/api/agentic-team/deliveries/nonexistent")
        assert resp.status_code == 404

    def test_disabled_returns_503(self, disabled_client):
        resp = disabled_client.get("/api/agentic-team/deliveries/del-001")
        assert resp.status_code == 503
