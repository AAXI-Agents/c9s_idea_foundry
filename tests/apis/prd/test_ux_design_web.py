"""Tests for UX design web-app endpoints (A2/A3 from Gap Analysis).

Tests POST /flow/ux/kickoff and GET /flow/ux/status/{run_id}.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

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


_FIND_RUN = (
    "crewai_productfeature_planner.mongodb.working_ideas.find_run_any_status"
)
_BG_TASK = (
    "crewai_productfeature_planner.apis.prd._route_ux_design._run_ux_design_background"
)
_SAVE_UX = (
    "crewai_productfeature_planner.apis.prd._route_ux_design.save_ux_design"
)


# ── POST /flow/ux/kickoff ────────────────────────────────────


class TestUXKickoffWeb:
    """Tests for POST /flow/ux/kickoff (web-app format)."""

    def test_kickoff_returns_202(self, client):
        """Successful kickoff returns 202 with generating status."""
        idea_doc = {
            "run_id": "r-1",
            "status": "completed",
            "ux_design_status": "",
            "idea": "Build a widget",
        }
        with patch(_FIND_RUN, return_value=idea_doc), patch(_BG_TASK):
            resp = client.post(
                "/flow/ux/kickoff",
                json={"run_id": "r-1"},
            )
        assert resp.status_code == 202
        body = resp.json()
        assert body["run_id"] == "r-1"
        assert body["ux_design_status"] == "generating"

    def test_kickoff_run_not_found(self, client):
        """Missing run returns 404."""
        with patch(_FIND_RUN, return_value=None):
            resp = client.post(
                "/flow/ux/kickoff",
                json={"run_id": "missing"},
            )
        assert resp.status_code == 404

    def test_kickoff_not_completed(self, client):
        """Non-completed PRD returns 409."""
        idea_doc = {"run_id": "r-2", "status": "inprogress"}
        with patch(_FIND_RUN, return_value=idea_doc):
            resp = client.post(
                "/flow/ux/kickoff",
                json={"run_id": "r-2"},
            )
        assert resp.status_code == 409
        assert "completed" in resp.json()["detail"].lower()

    def test_kickoff_already_generating(self, client):
        """Already generating returns 409."""
        idea_doc = {
            "run_id": "r-3",
            "status": "completed",
            "ux_design_status": "generating",
        }
        with patch(_FIND_RUN, return_value=idea_doc):
            resp = client.post(
                "/flow/ux/kickoff",
                json={"run_id": "r-3"},
            )
        assert resp.status_code == 409
        assert "already" in resp.json()["detail"].lower()

    def test_kickoff_missing_run_id(self, client):
        """Missing run_id in body returns 422."""
        resp = client.post("/flow/ux/kickoff", json={})
        assert resp.status_code == 422


# ── GET /flow/ux/status/{run_id} ─────────────────────────────


class TestUXDesignStatus:
    """Tests for GET /flow/ux/status/{run_id}."""

    def test_status_not_started(self, client):
        """No UX design started returns empty status."""
        idea_doc = {"run_id": "r-10", "status": "completed"}
        with patch(_FIND_RUN, return_value=idea_doc):
            resp = client.get("/flow/ux/status/r-10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["run_id"] == "r-10"
        assert body["status"] == ""
        assert body["current_step"] == ""
        assert body["design_md_ready"] is False
        assert body["figma_uploaded"] is False
        assert body["figma_url"] is None

    def test_status_generating(self, client):
        """In-progress UX design returns generating status."""
        idea_doc = {
            "run_id": "r-11",
            "status": "completed",
            "ux_design_status": "generating",
        }
        with patch(_FIND_RUN, return_value=idea_doc):
            resp = client.get("/flow/ux/status/r-11")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "generating"
        assert body["current_step"] == "Running UX design agents"
        assert body["design_md_ready"] is False

    def test_status_completed(self, client):
        """Completed UX design returns full status with content flag."""
        idea_doc = {
            "run_id": "r-12",
            "status": "completed",
            "ux_design_status": "completed",
            "ux_design_content": "# UX Design\n\nSome design content",
        }
        with patch(_FIND_RUN, return_value=idea_doc):
            resp = client.get("/flow/ux/status/r-12")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["current_step"] == "Completed"
        assert body["design_md_ready"] is True
        assert body["stitch_completed"] is True

    def test_status_with_figma_url(self, client):
        """Figma URL is returned when available."""
        idea_doc = {
            "run_id": "r-13",
            "status": "completed",
            "ux_design_status": "completed",
            "ux_design_content": "# UX",
            "figma_url": "https://figma.com/file/abc",
        }
        with patch(_FIND_RUN, return_value=idea_doc):
            resp = client.get("/flow/ux/status/r-13")
        assert resp.status_code == 200
        body = resp.json()
        assert body["figma_uploaded"] is True
        assert body["figma_url"] == "https://figma.com/file/abc"

    def test_status_run_not_found(self, client):
        """Missing run returns 404."""
        with patch(_FIND_RUN, return_value=None):
            resp = client.get("/flow/ux/status/missing")
        assert resp.status_code == 404

    def test_status_fallback_to_figma_design_status(self, client):
        """Falls back to figma_design_status field if ux_design_status is empty."""
        idea_doc = {
            "run_id": "r-14",
            "status": "completed",
            "figma_design_status": "completed",
            "ux_design_content": "# Design",
        }
        with patch(_FIND_RUN, return_value=idea_doc):
            resp = client.get("/flow/ux/status/r-14")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"

    def test_status_error_field(self, client):
        """Error field is surfaced when present."""
        idea_doc = {
            "run_id": "r-15",
            "status": "completed",
            "ux_design_status": "",
            "ux_design_error": "LLM rate limit exceeded",
        }
        with patch(_FIND_RUN, return_value=idea_doc):
            resp = client.get("/flow/ux/status/r-15")
        assert resp.status_code == 200
        body = resp.json()
        assert body["error"] == "LLM rate limit exceeded"

    def test_response_fields(self, client):
        """Response contains exactly the expected fields."""
        idea_doc = {"run_id": "r-16", "status": "completed"}
        with patch(_FIND_RUN, return_value=idea_doc):
            resp = client.get("/flow/ux/status/r-16")
        body = resp.json()
        expected = {
            "run_id", "status", "current_step", "design_md_ready",
            "stitch_completed", "figma_uploaded", "figma_url", "error",
        }
        assert set(body.keys()) == expected
