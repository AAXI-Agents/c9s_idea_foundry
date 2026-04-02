"""Tests for GET /flow/runs/{run_id}/activity endpoint."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app
from crewai_productfeature_planner.apis.shared import runs


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


class TestActivityLog:
    """Tests for GET /flow/runs/{run_id}/activity."""

    def test_activity_returns_events(self, client):
        """Should return activity events from agentInteraction collection."""
        mock_docs = [
            {
                "interaction_id": "abc123",
                "source": "api",
                "intent": "create_prd",
                "agent_response": "Starting PRD...",
                "run_id": "run-123",
                "user_id": "user-1",
                "created_at": "2026-03-20T10:30:00Z",
                "predicted_next_step": None,
            },
            {
                "interaction_id": "def456",
                "source": "api",
                "intent": "approve",
                "agent_response": "Section approved.",
                "run_id": "run-123",
                "user_id": "user-1",
                "created_at": "2026-03-20T10:35:00Z",
                "predicted_next_step": {"next_step": "review", "confidence": 0.9},
            },
        ]
        with patch(
            "crewai_productfeature_planner.mongodb.agent_interactions.find_interactions",
            return_value=mock_docs,
        ) as mock_find:
            resp = client.get("/flow/runs/run-123/activity")

        assert resp.status_code == 200
        body = resp.json()
        assert body["run_id"] == "run-123"
        assert body["count"] == 2
        assert len(body["events"]) == 2
        assert body["events"][0]["interaction_id"] == "abc123"
        assert body["events"][1]["predicted_next_step"]["confidence"] == 0.9
        mock_find.assert_called_once_with(run_id="run-123", limit=50)

    def test_activity_respects_limit(self, client):
        """Should pass limit query param to find_interactions."""
        with patch(
            "crewai_productfeature_planner.mongodb.agent_interactions.find_interactions",
            return_value=[],
        ) as mock_find:
            resp = client.get("/flow/runs/run-123/activity?limit=10")

        assert resp.status_code == 200
        mock_find.assert_called_once_with(run_id="run-123", limit=10)

    def test_activity_empty_list(self, client):
        """Should return empty events list when no interactions exist."""
        with patch(
            "crewai_productfeature_planner.mongodb.agent_interactions.find_interactions",
            return_value=[],
        ):
            resp = client.get("/flow/runs/no-such-run/activity")

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["events"] == []

    def test_activity_db_error_returns_500(self, client):
        """Should return 500 when database query fails."""
        with patch(
            "crewai_productfeature_planner.mongodb.agent_interactions.find_interactions",
            side_effect=Exception("DB connection failed"),
        ):
            resp = client.get("/flow/runs/run-123/activity")

        assert resp.status_code == 500

    def test_activity_limit_validation(self, client):
        """Should reject limit values outside 1-500 range."""
        resp = client.get("/flow/runs/run-123/activity?limit=0")
        assert resp.status_code == 422

        resp = client.get("/flow/runs/run-123/activity?limit=501")
        assert resp.status_code == 422
