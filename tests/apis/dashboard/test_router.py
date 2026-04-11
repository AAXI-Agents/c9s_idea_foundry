"""Tests for GET /dashboard/stats endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import PyMongoError

from crewai_productfeature_planner.apis import app


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


# ── Helpers ───────────────────────────────────────────────────


_PATCH_GET_DB = (
    "crewai_productfeature_planner.mongodb.working_ideas._common.get_db"
)


def _mock_aggregate(results):
    """Return a mock db where aggregate() returns *results*."""
    coll = MagicMock()
    coll.aggregate.return_value = results
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=coll)
    return db


# ── Tests ─────────────────────────────────────────────────────


class TestDashboardStats:
    """Tests for GET /dashboard/stats."""

    def test_returns_zeros_when_no_ideas(self, client):
        """Empty collection returns all-zero stats."""
        with patch(_PATCH_GET_DB, return_value=_mock_aggregate([])):
            resp = client.get("/dashboard/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "total_ideas": 0,
            "in_development": 0,
            "prd_completed": 0,
            "ideas_in_progress": 0,
            "uxd_completed": 0,
        }

    def test_aggregates_counts(self, client):
        """Aggregated counts are returned correctly."""
        agg_result = [
            {
                "_id": None,
                "total_ideas": 15,
                "in_development": 5,
                "prd_completed": 8,
                "ideas_in_progress": 3,
                "uxd_completed": 2,
            }
        ]
        with patch(_PATCH_GET_DB, return_value=_mock_aggregate(agg_result)):
            resp = client.get("/dashboard/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_ideas"] == 15
        assert body["in_development"] == 5
        assert body["prd_completed"] == 8
        assert body["ideas_in_progress"] == 3
        assert body["uxd_completed"] == 2

    def test_returns_zeros_on_db_error(self, client):
        """Database error returns zeros (graceful degradation)."""
        db = MagicMock()
        coll = MagicMock()
        coll.aggregate.side_effect = PyMongoError("connection lost")
        db.__getitem__ = MagicMock(return_value=coll)
        with patch(_PATCH_GET_DB, return_value=db):
            resp = client.get("/dashboard/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_ideas"] == 0

    def test_response_model_fields(self, client):
        """Response contains exactly the expected fields."""
        with patch(_PATCH_GET_DB, return_value=_mock_aggregate([])):
            resp = client.get("/dashboard/stats")
        body = resp.json()
        expected_keys = {
            "total_ideas", "in_development", "prd_completed",
            "ideas_in_progress", "uxd_completed",
        }
        assert set(body.keys()) == expected_keys
