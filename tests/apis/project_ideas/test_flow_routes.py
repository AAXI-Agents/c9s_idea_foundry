"""Tests for flow integration routes (Phase 2).

POST /{idea_id}/start
GET  /{idea_id}/progress
POST /{idea_id}/resume
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app

_ROUTE = "crewai_productfeature_planner.apis.project_ideas._route_flow"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _idea_doc(**overrides):
    doc = {
        "idea_id": "idea-001",
        "project_id": "proj-1",
        "title": "Test Idea",
        "description": "A detailed description",
        "status": "draft",
        "features": [],
        "overall_completion": 0.0,
        "active_run_id": None,
        "run_ids": [],
        "ideation_session_id": None,
        "design_url": None,
        "design_url_type": None,
        "created_by": "user-1",
        "created_at": "2026-05-01T00:00:00Z",
        "updated_at": "2026-05-01T00:00:00Z",
        "organization_id": "org-1",
        "enterprise_id": "ent-1",
    }
    doc.update(overrides)
    return doc


class TestStartIdeaFlow:
    def test_starts_flow_for_draft_idea(self, client):
        doc = _idea_doc(status="draft")
        with (
            patch(f"{_ROUTE}.get_idea", return_value=doc),
            patch(f"{_ROUTE}.set_active_run", return_value=True),
            patch(f"{_ROUTE}.update_idea_status", return_value=True),
            patch(
                "crewai_productfeature_planner.mongodb.crew_jobs.find_active_job",
                return_value=None,
            ),
            patch(
                "crewai_productfeature_planner.mongodb.crew_jobs.create_job",
            ),
            patch(
                "crewai_productfeature_planner.mongodb.working_ideas.save_project_ref",
            ),
            patch(
                "crewai_productfeature_planner.apis.prd.service.run_prd_flow",
            ),
        ):
            resp = client.post("/projects/proj-1/ideas/idea-001/start")
        assert resp.status_code == 202
        body = resp.json()
        assert body["idea_id"] == "idea-001"
        assert "run_id" in body
        assert body["status"] == "in_progress"

    def test_rejects_in_progress_idea(self, client):
        doc = _idea_doc(status="in_progress")
        with patch(f"{_ROUTE}.get_idea", return_value=doc):
            resp = client.post("/projects/proj-1/ideas/idea-001/start")
        assert resp.status_code == 409

    def test_rejects_with_active_run(self, client):
        doc = _idea_doc(status="draft", active_run_id="run-existing")
        with patch(f"{_ROUTE}.get_idea", return_value=doc):
            resp = client.post("/projects/proj-1/ideas/idea-001/start")
        assert resp.status_code == 409

    def test_404_not_found(self, client):
        with patch(f"{_ROUTE}.get_idea", return_value=None):
            resp = client.post("/projects/proj-1/ideas/missing/start")
        assert resp.status_code == 404

    def test_409_active_job_exists(self, client):
        doc = _idea_doc(status="draft")
        with (
            patch(f"{_ROUTE}.get_idea", return_value=doc),
            patch(
                "crewai_productfeature_planner.mongodb.crew_jobs.find_active_job",
                return_value={"job_id": "other-job", "status": "running"},
            ),
        ):
            resp = client.post("/projects/proj-1/ideas/idea-001/start")
        assert resp.status_code == 409


class TestGetIdeaProgress:
    def test_no_active_run(self, client):
        doc = _idea_doc(status="draft", active_run_id=None)
        with patch(f"{_ROUTE}.get_idea", return_value=doc):
            resp = client.get("/projects/proj-1/ideas/idea-001/progress")
        assert resp.status_code == 200
        body = resp.json()
        assert body["active_run_id"] is None
        assert body["flow_status"] is None

    def test_with_in_memory_run(self, client):
        from crewai_productfeature_planner.apis.shared import FlowRun, FlowStatus, runs

        run_id = "test-run-progress"
        run = FlowRun(run_id=run_id, flow_name="prd", status=FlowStatus.RUNNING)
        run.current_section_key = "executive_summary"
        runs[run_id] = run

        doc = _idea_doc(status="in_progress", active_run_id=run_id)
        try:
            with patch(f"{_ROUTE}.get_idea", return_value=doc):
                resp = client.get("/projects/proj-1/ideas/idea-001/progress")
            assert resp.status_code == 200
            body = resp.json()
            assert body["flow_status"] == "running"
            assert body["active_run_id"] == run_id
        finally:
            runs.pop(run_id, None)

    def test_404_not_found(self, client):
        with patch(f"{_ROUTE}.get_idea", return_value=None):
            resp = client.get("/projects/proj-1/ideas/missing/progress")
        assert resp.status_code == 404


class TestResumeIdeaFlow:
    def test_resumes_paused_flow(self, client):
        doc = _idea_doc(status="in_progress", active_run_id="run-paused")
        job = {"job_id": "run-paused", "status": "paused"}
        with (
            patch(f"{_ROUTE}.get_idea", return_value=doc),
            patch(
                "crewai_productfeature_planner.mongodb.crew_jobs.find_job",
                return_value=job,
            ),
            patch(
                "crewai_productfeature_planner.apis.prd.service.resume_prd_flow",
            ),
        ):
            resp = client.post("/projects/proj-1/ideas/idea-001/resume")
        assert resp.status_code == 202
        assert resp.json()["run_id"] == "run-paused"

    def test_409_no_active_run(self, client):
        doc = _idea_doc(status="draft", active_run_id=None)
        with patch(f"{_ROUTE}.get_idea", return_value=doc):
            resp = client.post("/projects/proj-1/ideas/idea-001/resume")
        assert resp.status_code == 409

    def test_409_flow_not_paused(self, client):
        doc = _idea_doc(status="in_progress", active_run_id="run-active")
        job = {"job_id": "run-active", "status": "running"}
        with (
            patch(f"{_ROUTE}.get_idea", return_value=doc),
            patch(
                "crewai_productfeature_planner.mongodb.crew_jobs.find_job",
                return_value=job,
            ),
        ):
            resp = client.post("/projects/proj-1/ideas/idea-001/resume")
        assert resp.status_code == 409

    def test_404_not_found(self, client):
        with patch(f"{_ROUTE}.get_idea", return_value=None):
            resp = client.post("/projects/proj-1/ideas/missing/resume")
        assert resp.status_code == 404
