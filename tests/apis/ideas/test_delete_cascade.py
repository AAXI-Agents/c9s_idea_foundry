"""Tests for DELETE /ideas/{run_id} with full cascade support."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app

_DELETE_MOD = "crewai_productfeature_planner.apis.ideas.delete_idea"
_QUERIES = "crewai_productfeature_planner.mongodb.working_ideas._queries"
_STATUS = "crewai_productfeature_planner.mongodb.working_ideas._status"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _make_idea_doc(**overrides):
    doc = {
        "run_id": "run001",
        "idea": "Build a fitness tracker",
        "finalized_idea": "",
        "status": "completed",
        "project_id": "proj1",
        "created_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-02T00:00:00Z",
        "section": {"summary": [{}], "requirements": [{}], "ux_design": [{}]},
        "executive_summary": [],
        "jira_phase": "",
        "ux_design_status": "completed",
    }
    doc.update(overrides)
    return doc


# ── Basic soft-delete (200 JSON response) ────────────────────


class TestDeleteBasic:
    def test_soft_delete_returns_200_with_cascade(self, client):
        doc = _make_idea_doc()
        with (
            patch(f"{_QUERIES}.find_run_any_status", return_value=doc),
            patch(f"{_STATUS}.mark_deleted") as mock_delete,
            patch(f"{_DELETE_MOD}.response_cache") as mock_cache,
            patch(f"{_DELETE_MOD}._cascade_ideation_session", return_value=""),
            patch(f"{_DELETE_MOD}._cascade_product_requirements", return_value={"jira_cleared": 0, "confluence_cleared": 0}),
            patch(f"{_DELETE_MOD}._clear_ux_state", return_value=1),
            patch(f"{_DELETE_MOD}._broadcast_idea_deleted"),
        ):
            resp = client.delete("/ideas/run001")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "deleted"
        assert body["run_id"] == "run001"
        assert "cascaded" in body
        mock_delete.assert_called_once_with("run001")
        mock_cache.invalidate.assert_called_once_with("ideas")

    def test_not_found_returns_404(self, client):
        with patch(f"{_QUERIES}.find_run_any_status", return_value=None):
            resp = client.delete("/ideas/nonexistent")
        assert resp.status_code == 404


# ── 409 for in-flight ideas ──────────────────────────────────


class TestDeleteInFlight:
    def test_inprogress_returns_409(self, client):
        doc = _make_idea_doc(status="inprogress")
        with patch(f"{_QUERIES}.find_run_any_status", return_value=doc):
            resp = client.delete("/ideas/run001")
        assert resp.status_code == 409
        assert "Pause" in resp.json()["detail"]

    def test_paused_allows_delete(self, client):
        doc = _make_idea_doc(status="paused")
        with (
            patch(f"{_QUERIES}.find_run_any_status", return_value=doc),
            patch(f"{_STATUS}.mark_deleted"),
            patch(f"{_DELETE_MOD}.response_cache"),
            patch(f"{_DELETE_MOD}._cascade_ideation_session", return_value=""),
            patch(f"{_DELETE_MOD}._cascade_product_requirements", return_value={"jira_cleared": 0, "confluence_cleared": 0}),
            patch(f"{_DELETE_MOD}._clear_ux_state", return_value=0),
            patch(f"{_DELETE_MOD}._broadcast_idea_deleted"),
        ):
            resp = client.delete("/ideas/run001")
        assert resp.status_code == 200

    def test_completed_allows_delete(self, client):
        doc = _make_idea_doc(status="completed")
        with (
            patch(f"{_QUERIES}.find_run_any_status", return_value=doc),
            patch(f"{_STATUS}.mark_deleted"),
            patch(f"{_DELETE_MOD}.response_cache"),
            patch(f"{_DELETE_MOD}._cascade_ideation_session", return_value=""),
            patch(f"{_DELETE_MOD}._cascade_product_requirements", return_value={"jira_cleared": 0, "confluence_cleared": 0}),
            patch(f"{_DELETE_MOD}._clear_ux_state", return_value=0),
            patch(f"{_DELETE_MOD}._broadcast_idea_deleted"),
        ):
            resp = client.delete("/ideas/run001")
        assert resp.status_code == 200

    def test_failed_allows_delete(self, client):
        doc = _make_idea_doc(status="failed")
        with (
            patch(f"{_QUERIES}.find_run_any_status", return_value=doc),
            patch(f"{_STATUS}.mark_deleted"),
            patch(f"{_DELETE_MOD}.response_cache"),
            patch(f"{_DELETE_MOD}._cascade_ideation_session", return_value=""),
            patch(f"{_DELETE_MOD}._cascade_product_requirements", return_value={"jira_cleared": 0, "confluence_cleared": 0}),
            patch(f"{_DELETE_MOD}._clear_ux_state", return_value=0),
            patch(f"{_DELETE_MOD}._broadcast_idea_deleted"),
        ):
            resp = client.delete("/ideas/run001")
        assert resp.status_code == 200


# ── Cascade behavior ─────────────────────────────────────────


class TestDeleteCascade:
    def test_cascade_ideation_session(self, client):
        doc = _make_idea_doc()
        with (
            patch(f"{_QUERIES}.find_run_any_status", return_value=doc),
            patch(f"{_STATUS}.mark_deleted"),
            patch(f"{_DELETE_MOD}.response_cache"),
            patch(f"{_DELETE_MOD}._cascade_ideation_session", return_value="sess_abc") as mock_cascade_sess,
            patch(f"{_DELETE_MOD}._cascade_product_requirements", return_value={"jira_cleared": 2, "confluence_cleared": 1}),
            patch(f"{_DELETE_MOD}._clear_ux_state", return_value=1),
            patch(f"{_DELETE_MOD}._broadcast_idea_deleted"),
        ):
            resp = client.delete("/ideas/run001")

        body = resp.json()
        assert body["cascaded"]["ideation_session_id"] == "sess_abc"
        assert body["cascaded"]["jira_links_cleared"] == 2
        assert body["cascaded"]["confluence_links_cleared"] == 1
        assert body["cascaded"]["ux_runs_cleared"] == 1
        mock_cascade_sess.assert_called_once()

    def test_cascade_sections_counted_from_doc(self, client):
        doc = _make_idea_doc(section={
            "summary": [{}],
            "requirements": [{}],
            "architecture": [{}],
        })
        with (
            patch(f"{_QUERIES}.find_run_any_status", return_value=doc),
            patch(f"{_STATUS}.mark_deleted"),
            patch(f"{_DELETE_MOD}.response_cache"),
            patch(f"{_DELETE_MOD}._cascade_ideation_session", return_value=""),
            patch(f"{_DELETE_MOD}._cascade_product_requirements", return_value={"jira_cleared": 0, "confluence_cleared": 0}),
            patch(f"{_DELETE_MOD}._clear_ux_state", return_value=0),
            patch(f"{_DELETE_MOD}._broadcast_idea_deleted"),
        ):
            resp = client.delete("/ideas/run001")

        assert resp.json()["cascaded"]["sections_count"] == 3

    def test_websocket_broadcast_called(self, client):
        doc = _make_idea_doc()
        with (
            patch(f"{_QUERIES}.find_run_any_status", return_value=doc),
            patch(f"{_STATUS}.mark_deleted"),
            patch(f"{_DELETE_MOD}.response_cache"),
            patch(f"{_DELETE_MOD}._cascade_ideation_session", return_value=""),
            patch(f"{_DELETE_MOD}._cascade_product_requirements", return_value={"jira_cleared": 0, "confluence_cleared": 0}),
            patch(f"{_DELETE_MOD}._clear_ux_state", return_value=0),
            patch(f"{_DELETE_MOD}._broadcast_idea_deleted") as mock_ws,
        ):
            resp = client.delete("/ideas/run001")

        assert resp.status_code == 200
        mock_ws.assert_called_once_with("run001")


# ── Remote purge ─────────────────────────────────────────────


class TestDeleteRemotePurge:
    def test_purge_remote_false_by_default(self, client):
        doc = _make_idea_doc()
        with (
            patch(f"{_QUERIES}.find_run_any_status", return_value=doc),
            patch(f"{_STATUS}.mark_deleted"),
            patch(f"{_DELETE_MOD}.response_cache"),
            patch(f"{_DELETE_MOD}._cascade_ideation_session", return_value=""),
            patch(f"{_DELETE_MOD}._cascade_product_requirements", return_value={"jira_cleared": 0, "confluence_cleared": 0}),
            patch(f"{_DELETE_MOD}._clear_ux_state", return_value=0),
            patch(f"{_DELETE_MOD}._broadcast_idea_deleted"),
            patch(f"{_DELETE_MOD}._purge_remote_integrations") as mock_purge,
        ):
            resp = client.delete("/ideas/run001")

        assert resp.status_code == 200
        mock_purge.assert_not_called()
        assert resp.json()["cascaded"]["remote_purge"]["attempted"] is False

    def test_purge_remote_true_success(self, client):
        from crewai_productfeature_planner.apis.ideas.models import RemotePurgeResult

        doc = _make_idea_doc()
        purge_result = RemotePurgeResult(
            attempted=True,
            jira_deleted=["IDEA-42"],
            confluence_deleted=["12345678"],
            errors=[],
        )
        with (
            patch(f"{_QUERIES}.find_run_any_status", return_value=doc),
            patch(f"{_STATUS}.mark_deleted"),
            patch(f"{_DELETE_MOD}.response_cache"),
            patch(f"{_DELETE_MOD}._cascade_ideation_session", return_value=""),
            patch(f"{_DELETE_MOD}._cascade_product_requirements", return_value={"jira_cleared": 1, "confluence_cleared": 1}),
            patch(f"{_DELETE_MOD}._clear_ux_state", return_value=0),
            patch(f"{_DELETE_MOD}._broadcast_idea_deleted"),
            patch(f"{_DELETE_MOD}._purge_remote_integrations", return_value=purge_result),
        ):
            resp = client.delete("/ideas/run001?purge_remote=true")

        assert resp.status_code == 200
        body = resp.json()
        assert body["cascaded"]["remote_purge"]["attempted"] is True
        assert body["cascaded"]["remote_purge"]["jira_deleted"] == ["IDEA-42"]
        assert body["cascaded"]["remote_purge"]["confluence_deleted"] == ["12345678"]

    def test_purge_remote_partial_failure_returns_502(self, client):
        from crewai_productfeature_planner.apis.ideas.models import RemotePurgeResult

        doc = _make_idea_doc()
        purge_result = RemotePurgeResult(
            attempted=True,
            jira_deleted=["IDEA-42"],
            confluence_deleted=[],
            errors=["confluence:123:timeout"],
        )
        with (
            patch(f"{_QUERIES}.find_run_any_status", return_value=doc),
            patch(f"{_STATUS}.mark_deleted"),
            patch(f"{_DELETE_MOD}.response_cache"),
            patch(f"{_DELETE_MOD}._cascade_ideation_session", return_value=""),
            patch(f"{_DELETE_MOD}._cascade_product_requirements", return_value={"jira_cleared": 1, "confluence_cleared": 1}),
            patch(f"{_DELETE_MOD}._clear_ux_state", return_value=0),
            patch(f"{_DELETE_MOD}._broadcast_idea_deleted"),
            patch(f"{_DELETE_MOD}._purge_remote_integrations", return_value=purge_result),
        ):
            resp = client.delete("/ideas/run001?purge_remote=true")

        # 502 signals partial purge failure — the soft-delete still committed
        assert resp.status_code == 502
        body = resp.json()["detail"]
        assert body["status"] == "deleted"
        assert body["cascaded"]["remote_purge"]["errors"] == ["confluence:123:timeout"]


# ── crewJobs mirror ──────────────────────────────────────────


class TestDeleteCrewJobsMirror:
    def test_crew_jobs_updated(self, client):
        doc = _make_idea_doc()
        with (
            patch(f"{_QUERIES}.find_run_any_status", return_value=doc),
            patch(f"{_STATUS}.mark_deleted"),
            patch(f"{_DELETE_MOD}.response_cache"),
            patch(f"{_DELETE_MOD}._cascade_ideation_session", return_value=""),
            patch(f"{_DELETE_MOD}._cascade_product_requirements", return_value={"jira_cleared": 0, "confluence_cleared": 0}),
            patch(f"{_DELETE_MOD}._clear_ux_state", return_value=0),
            patch(f"{_DELETE_MOD}._broadcast_idea_deleted"),
            patch(
                "crewai_productfeature_planner.mongodb.crew_jobs.repository.update_job_status"
            ) as mock_job,
        ):
            resp = client.delete("/ideas/run001")

        assert resp.status_code == 200
        mock_job.assert_called_once_with("run001", "deleted")
