"""Tests for activity enrichment and agent roster features."""

from __future__ import annotations

from unittest.mock import ANY, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app
from crewai_productfeature_planner.apis.prd.models import PRDDraft, ExecutiveSummaryDraft


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
    from crewai_productfeature_planner.apis.shared import runs
    runs.clear()
    yield
    runs.clear()


class TestActivityEnrichment:
    """Tests for enriched activity event fields."""

    def test_activity_includes_new_fields(self, client):
        """Activity events should include agent_id, severity, tokens_delta, cost_usd_delta."""
        mock_docs = [
            {
                "interaction_id": "int1",
                "source": "crew",
                "intent": "section_draft",
                "agent_response": "Drafted overview section",
                "run_id": "run-enrich",
                "created_at": "2026-03-20T10:30:00Z",
                "metadata": {
                    "agent_id": "product_manager",
                    "tokens_delta": 1500,
                    "cost_usd_delta": 0.015,
                    "is_error": False,
                },
            },
        ]
        with patch(
            "crewai_productfeature_planner.mongodb.agent_interactions.find_interactions",
            return_value=mock_docs,
        ):
            resp = client.get("/flow/runs/run-enrich/activity")

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        evt = body["events"][0]
        assert evt["agent_id"] == "product_manager"
        assert evt["tokens_delta"] == 1500
        assert evt["cost_usd_delta"] == 0.015
        # severity should be "info" for non-error
        assert evt.get("severity") in ("info", None, "")

    def test_activity_error_severity(self, client):
        """Events with is_error metadata should have severity='error'."""
        mock_docs = [
            {
                "interaction_id": "int2",
                "source": "crew",
                "intent": "error",
                "agent_response": "Agent failed",
                "run_id": "run-err",
                "created_at": "2026-03-20T10:30:00Z",
                "metadata": {
                    "is_error": True,
                    "agent_id": "staff_engineer",
                },
            },
        ]
        with patch(
            "crewai_productfeature_planner.mongodb.agent_interactions.find_interactions",
            return_value=mock_docs,
        ):
            resp = client.get("/flow/runs/run-err/activity")

        assert resp.status_code == 200
        evt = resp.json()["events"][0]
        assert evt["severity"] == "error"

    def test_activity_cost_tracking_available(self, client):
        """Response should include cost_tracking_available field."""
        with patch(
            "crewai_productfeature_planner.mongodb.agent_interactions.find_interactions",
            return_value=[],
        ):
            resp = client.get("/flow/runs/run-track/activity")

        assert resp.status_code == 200
        body = resp.json()
        assert "cost_tracking_available" in body


class TestAgentRoster:
    """Tests for agent roster on GET /flow/runs/{run_id}."""

    def _restore_state(self):
        """Return a mock restore_prd_state result."""
        draft = PRDDraft.create_empty()
        exec_summary = ExecutiveSummaryDraft()
        return ("Test idea", draft, exec_summary, "", [], [])

    def test_roster_on_db_run(self, client):
        """GET /flow/runs/{run_id} for a DB-reconstructed run should include agents."""
        job_doc = {
            "run_id": "run-roster",
            "flow_name": "prd",
            "status": "completed",
            "queued_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T01:00:00Z",
            "completed_at": "2026-01-01T02:00:00Z",
        }

        interactions = [
            {
                "interaction_id": "i1",
                "source": "crew",
                "intent": "section_draft",
                "agent_response": "Draft done",
                "run_id": "run-roster",
                "created_at": "2026-01-01T00:30:00Z",
                "metadata": {
                    "agent_id": "product_manager",
                    "tokens_delta": 500,
                    "cost_usd_delta": 0.005,
                },
            },
        ]

        registry_agents = [
            {
                "agent_id": "product_manager",
                "display_name": "Product Manager",
                "role": "pm",
                "title": "Senior PM",
                "reports_to": None,
                "status": "active",
            },
        ]

        with (
            patch(
                "crewai_productfeature_planner.apis.prd.router.find_job",
                return_value=job_doc,
            ),
            patch(
                "crewai_productfeature_planner.apis.prd.router.restore_prd_state",
                return_value=self._restore_state(),
            ),
            patch(
                "crewai_productfeature_planner.mongodb.working_ideas.find_run_any_status",
                return_value={"run_id": "run-roster", "idea": "Test"},
            ),
            patch(
                "crewai_productfeature_planner.mongodb.agent_interactions.find_interactions",
                return_value=interactions,
            ),
            patch(
                "crewai_productfeature_planner.mongodb.agent_registry.list_agents",
                return_value=registry_agents,
            ),
        ):
            resp = client.get("/flow/runs/run-roster")

        assert resp.status_code == 200
        body = resp.json()
        assert "agents" in body
        assert "cost_tracking_available" in body
        assert body["cost_tracking_available"] is True
        assert len(body["agents"]) == 1
        assert body["agents"][0]["id"] == "product_manager"
        assert body["agents"][0]["tokens_used"] == 500

    def test_roster_empty_when_no_interactions(self, client):
        """Agent roster should be empty when no interactions exist for the run."""
        job_doc = {
            "run_id": "run-empty",
            "flow_name": "prd",
            "status": "completed",
            "queued_at": "2026-01-01T00:00:00Z",
        }

        with (
            patch(
                "crewai_productfeature_planner.apis.prd.router.find_job",
                return_value=job_doc,
            ),
            patch(
                "crewai_productfeature_planner.apis.prd.router.restore_prd_state",
                return_value=self._restore_state(),
            ),
            patch(
                "crewai_productfeature_planner.mongodb.working_ideas.find_run_any_status",
                return_value={"run_id": "run-empty", "idea": "Test"},
            ),
            patch(
                "crewai_productfeature_planner.mongodb.agent_interactions.find_interactions",
                return_value=[],
            ),
            patch(
                "crewai_productfeature_planner.mongodb.agent_registry.list_agents",
                return_value=[],
            ),
        ):
            resp = client.get("/flow/runs/run-empty")

        assert resp.status_code == 200
        body = resp.json()
        assert body["agents"] == []
        assert body["cost_tracking_available"] is False
