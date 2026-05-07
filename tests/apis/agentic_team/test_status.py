"""Tests for Agentic Team status endpoints (_status.py)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from crewai_productfeature_planner.apis.agentic_team._status import router


@pytest.fixture
def app():
    """Create a test FastAPI app with the status router."""
    _app = FastAPI()
    _app.include_router(router)
    return _app


@pytest.fixture
def client(app):
    """Create an async test client."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ── GET /api/agentic-team/status/{idea_id} ───────────────────


class TestGetAgentStatus:
    """Test the idea status endpoint."""

    @pytest.mark.asyncio
    async def test_returns_status_on_success(self, client):
        mock_result = {
            "tasks": [{"key": "PRD-10", "status": "completed"}],
            "completion_pct": 100,
        }

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._status.AGENTIC_TEAM_ENABLED",
            True,
        ), patch(
            "crewai_productfeature_planner.apis.agentic_team._service.get_idea_agent_status",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.get("/api/agentic-team/status/idea-abc")
            assert resp.status_code == 200
            data = resp.json()
            assert data["completion_pct"] == 100

    @pytest.mark.asyncio
    async def test_returns_503_when_disabled(self, client):
        with patch(
            "crewai_productfeature_planner.apis.agentic_team._status.AGENTIC_TEAM_ENABLED",
            False,
        ):
            resp = await client.get("/api/agentic-team/status/idea-abc")
            assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_returns_502_on_service_failure(self, client):
        with patch(
            "crewai_productfeature_planner.apis.agentic_team._status.AGENTIC_TEAM_ENABLED",
            True,
        ), patch(
            "crewai_productfeature_planner.apis.agentic_team._service.get_idea_agent_status",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = await client.get("/api/agentic-team/status/idea-abc")
            assert resp.status_code == 502


# ── GET /api/agentic-team/dashboard ──────────────────────────


class TestGetDashboard:
    """Test the dashboard endpoint."""

    @pytest.mark.asyncio
    async def test_returns_dashboard_on_success(self, client):
        mock_result = {"active": 5, "queued": 10, "completed": 42}

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._status.AGENTIC_TEAM_ENABLED",
            True,
        ), patch(
            "crewai_productfeature_planner.apis.agentic_team._service.get_pipeline_dashboard",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.get("/api/agentic-team/dashboard")
            assert resp.status_code == 200
            assert resp.json()["active"] == 5

    @pytest.mark.asyncio
    async def test_returns_503_when_disabled(self, client):
        with patch(
            "crewai_productfeature_planner.apis.agentic_team._status.AGENTIC_TEAM_ENABLED",
            False,
        ):
            resp = await client.get("/api/agentic-team/dashboard")
            assert resp.status_code == 503


# ── GET /api/agentic-team/task/{issue_key} ───────────────────


class TestGetTaskPipelineStatus:
    """Test the single task status endpoint."""

    @pytest.mark.asyncio
    async def test_returns_task_status(self, client):
        mock_result = {"key": "PRD-10", "stage": "testing", "progress": 80}

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._status.AGENTIC_TEAM_ENABLED",
            True,
        ), patch(
            "crewai_productfeature_planner.apis.agentic_team._service.get_task_status",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.get("/api/agentic-team/task/PRD-10")
            assert resp.status_code == 200
            assert resp.json()["stage"] == "testing"

    @pytest.mark.asyncio
    async def test_returns_503_when_disabled(self, client):
        with patch(
            "crewai_productfeature_planner.apis.agentic_team._status.AGENTIC_TEAM_ENABLED",
            False,
        ):
            resp = await client.get("/api/agentic-team/task/PRD-10")
            assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_returns_502_on_service_failure(self, client):
        with patch(
            "crewai_productfeature_planner.apis.agentic_team._status.AGENTIC_TEAM_ENABLED",
            True,
        ), patch(
            "crewai_productfeature_planner.apis.agentic_team._service.get_task_status",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = await client.get("/api/agentic-team/task/PRD-10")
            assert resp.status_code == 502
