"""Tests for the PRD flow API endpoints and background service."""

import threading
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app
from crewai_productfeature_planner.apis.shared import (
    FlowRun,
    FlowStatus,
    approval_decisions,
    approval_events,
    approval_feedback,
    pause_requested,
    runs,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


@pytest.fixture()
def client():
    """Provide a fresh TestClient and clear stores between tests."""
    runs.clear()
    approval_events.clear()
    approval_decisions.clear()
    approval_feedback.clear()
    pause_requested.clear()
    with TestClient(app) as c:
        yield c
    runs.clear()
    approval_events.clear()
    approval_decisions.clear()
    approval_feedback.clear()
    pause_requested.clear()


# ── POST /flow/prd/kickoff ───────────────────────────────────


def test_kickoff_prd_returns_202(client):
    """A valid request should return 202 with a run_id."""
    with patch("crewai_productfeature_planner.apis.prd.router.run_prd_flow"):
        resp = client.post(
            "/flow/prd/kickoff",
            json={"idea": "Add dark mode to the dashboard"},
        )
    assert resp.status_code == 202
    body = resp.json()
    assert "run_id" in body
    assert body["flow_name"] == "prd"
    assert body["status"] == "pending"


def test_kickoff_prd_missing_idea(client):
    """Request without idea should return 422."""
    resp = client.post("/flow/prd/kickoff", json={})
    assert resp.status_code == 422


def test_kickoff_prd_empty_idea(client):
    """Empty string idea should be rejected."""
    resp = client.post("/flow/prd/kickoff", json={"idea": ""})
    assert resp.status_code == 422


def test_kickoff_prd_registers_run(client):
    """A run record should be stored in the in-memory store."""
    with patch("crewai_productfeature_planner.apis.prd.router.run_prd_flow"):
        resp = client.post(
            "/flow/prd/kickoff",
            json={"idea": "SSO integration"},
        )
    run_id = resp.json()["run_id"]
    assert run_id in runs
    assert runs[run_id].flow_name == "prd"


# ── GET /flow/runs/{run_id} ──────────────────────────────────


def test_get_run_status_found(client):
    """Should return the run details when the run_id exists."""
    with patch("crewai_productfeature_planner.apis.prd.router.run_prd_flow"):
        resp = client.post(
            "/flow/prd/kickoff",
            json={"idea": "Webhooks"},
        )
    run_id = resp.json()["run_id"]
    status_resp = client.get(f"/flow/runs/{run_id}")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["run_id"] == run_id
    assert body["flow_name"] == "prd"


def test_get_run_status_not_found(client):
    """Unknown run_id should return 404."""
    resp = client.get("/flow/runs/nonexistent")
    assert resp.status_code == 404


# ── run_prd_flow background task ─────────────────────────────


def test_run_prd_flow_success():
    """Successful flow should set status to COMPLETED."""
    from crewai_productfeature_planner.apis.prd.service import run_prd_flow

    runs.clear()
    run = FlowRun(run_id="test-ok", flow_name="prd")
    runs["test-ok"] = run

    with patch("crewai_productfeature_planner.flows.prd_flow.PRDFlow") as MockFlow:
        mock_instance = MagicMock()
        mock_instance.kickoff.return_value = "# Final PRD"
        mock_instance.state = MagicMock()
        MockFlow.return_value = mock_instance

        run_prd_flow("test-ok", "Some idea")

    assert run.status == FlowStatus.COMPLETED
    assert run.result == "# Final PRD"
    assert run.error is None


def test_run_prd_flow_failure():
    """Failed flow should set status to FAILED with error message."""
    from crewai_productfeature_planner.apis.prd.service import run_prd_flow

    runs.clear()
    run = FlowRun(run_id="test-fail", flow_name="prd")
    runs["test-fail"] = run

    with patch("crewai_productfeature_planner.flows.prd_flow.PRDFlow") as MockFlow:
        mock_instance = MagicMock()
        mock_instance.kickoff.side_effect = RuntimeError("LLM timeout")
        mock_instance.state = MagicMock()
        MockFlow.return_value = mock_instance

        run_prd_flow("test-fail", "Bad idea")

    assert run.status == FlowStatus.FAILED
    assert "LLM timeout" in run.error


def test_run_prd_flow_pause():
    """Paused flow should set status to PAUSED."""
    from crewai_productfeature_planner.apis.prd.service import run_prd_flow
    from crewai_productfeature_planner.flows.prd_flow import PauseRequested

    runs.clear()
    run = FlowRun(run_id="test-pause", flow_name="prd")
    runs["test-pause"] = run

    with patch("crewai_productfeature_planner.flows.prd_flow.PRDFlow") as MockFlow:
        mock_instance = MagicMock()
        mock_instance.kickoff.side_effect = PauseRequested()
        mock_instance.state = MagicMock()
        MockFlow.return_value = mock_instance

        run_prd_flow("test-pause", "Paused idea")

    assert run.status == FlowStatus.PAUSED
    assert run.error is None


# ── POST /flow/prd/approve ───────────────────────────────────


def test_approve_not_found(client):
    """Approving a non-existent run should 404."""
    resp = client.post(
        "/flow/prd/approve",
        json={"run_id": "nope", "approve": True},
    )
    assert resp.status_code == 404


def test_approve_wrong_status(client):
    """Approving a run not in awaiting_approval should 409."""
    run = FlowRun(run_id="r1", flow_name="prd", status=FlowStatus.RUNNING)
    runs["r1"] = run
    resp = client.post(
        "/flow/prd/approve",
        json={"run_id": "r1", "approve": True},
    )
    assert resp.status_code == 409


def test_approve_sets_decision(client):
    """Approve=true should set the decision and unblock the event."""
    run = FlowRun(
        run_id="r2", flow_name="prd", status=FlowStatus.AWAITING_APPROVAL
    )
    run.current_section_key = "executive_summary"
    runs["r2"] = run
    event = threading.Event()
    approval_events["r2"] = event

    resp = client.post(
        "/flow/prd/approve",
        json={"run_id": "r2", "approve": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "approved"
    assert body["section"] == "executive_summary"
    assert event.is_set()


def test_continue_sets_decision(client):
    """Approve=false should set the continue decision."""
    run = FlowRun(
        run_id="r3", flow_name="prd", status=FlowStatus.AWAITING_APPROVAL
    )
    run.current_section_key = "problem_statement"
    runs["r3"] = run
    event = threading.Event()
    approval_events["r3"] = event

    resp = client.post(
        "/flow/prd/approve",
        json={"run_id": "r3", "approve": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "continuing refinement"
    assert body["section"] == "problem_statement"


def test_approve_with_feedback(client):
    """approve=false + feedback should store feedback and report it."""
    run = FlowRun(
        run_id="r4", flow_name="prd", status=FlowStatus.AWAITING_APPROVAL
    )
    run.current_section_key = "functional_requirements"
    runs["r4"] = run
    event = threading.Event()
    approval_events["r4"] = event

    resp = client.post(
        "/flow/prd/approve",
        json={
            "run_id": "r4",
            "approve": False,
            "feedback": "Add more detail to the security section.",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "continuing refinement with user feedback"
    assert body["section"] == "functional_requirements"
    assert event.is_set()
    assert approval_feedback.get("r4") == "Add more detail to the security section."


def test_approve_true_ignores_feedback(client):
    """approve=true should finalize even if feedback is provided."""
    run = FlowRun(
        run_id="r5", flow_name="prd", status=FlowStatus.AWAITING_APPROVAL
    )
    run.current_section_key = "user_personas"
    runs["r5"] = run
    event = threading.Event()
    approval_events["r5"] = event

    resp = client.post(
        "/flow/prd/approve",
        json={
            "run_id": "r5",
            "approve": True,
            "feedback": "This should be ignored.",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "approved"
    assert body["section"] == "user_personas"
    # Feedback should NOT be stored when approving
    assert "r5" not in approval_feedback


# ── API naming convention ────────────────────────────────────


def test_flow_routes_follow_naming_convention(client):
    """All flow routes should match /flow/{name}/kickoff or /flow/{name}/approve."""
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    flow_kickoff_routes = [
        r for r in routes if r.startswith("/flow/") and r.endswith("/kickoff")
    ]
    assert len(flow_kickoff_routes) >= 1
    assert "/flow/prd/kickoff" in flow_kickoff_routes
    assert "/flow/prd/approve" in routes
    assert "/flow/prd/pause" in routes
    assert "/flow/prd/resume" in routes
    assert "/flow/prd/resumable" in routes


# ── POST /flow/prd/pause ─────────────────────────────────────


def test_pause_not_found(client):
    """Pausing a non-existent run should 404."""
    resp = client.post("/flow/prd/pause", json={"run_id": "nope"})
    assert resp.status_code == 404


def test_pause_wrong_status(client):
    """Pausing a completed run should 409."""
    run = FlowRun(run_id="r-done", flow_name="prd", status=FlowStatus.COMPLETED)
    runs["r-done"] = run
    resp = client.post("/flow/prd/pause", json={"run_id": "r-done"})
    assert resp.status_code == 409


def test_pause_awaiting_approval(client):
    """Pausing an awaiting_approval run should set flag and unblock event."""
    run = FlowRun(
        run_id="r-pause", flow_name="prd", status=FlowStatus.AWAITING_APPROVAL
    )
    run.current_section_key = "executive_summary"
    runs["r-pause"] = run
    event = threading.Event()
    approval_events["r-pause"] = event

    resp = client.post("/flow/prd/pause", json={"run_id": "r-pause"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "paused"
    assert body["section"] == "executive_summary"
    assert event.is_set()
    assert pause_requested.get("r-pause") is True


def test_pause_running(client):
    """Pausing a running run should set the flag without unblocking."""
    run = FlowRun(run_id="r-run", flow_name="prd", status=FlowStatus.RUNNING)
    run.current_section_key = "problem_statement"
    runs["r-run"] = run

    resp = client.post("/flow/prd/pause", json={"run_id": "r-run"})
    assert resp.status_code == 200
    assert pause_requested.get("r-run") is True


# ── GET /flow/prd/resumable ──────────────────────────────────


@patch("crewai_productfeature_planner.apis.prd.router.find_unfinalized")
def test_list_resumable_runs(mock_find, client):
    """Should return unfinalized runs from MongoDB."""
    mock_find.return_value = [
        {
            "run_id": "abc123",
            "idea": "Dark mode",
            "iteration": 3,
            "created_at": None,
            "sections": ["executive_summary", "problem_statement"],
        }
    ]
    resp = client.get("/flow/prd/resumable")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["runs"][0]["run_id"] == "abc123"
    assert body["runs"][0]["idea"] == "Dark mode"
    assert len(body["runs"][0]["sections"]) == 2


@patch("crewai_productfeature_planner.apis.prd.router.find_unfinalized")
def test_list_resumable_empty(mock_find, client):
    """Should return empty list when no resumable runs."""
    mock_find.return_value = []
    resp = client.get("/flow/prd/resumable")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["runs"] == []


# ── POST /flow/prd/resume ────────────────────────────────────


@patch("crewai_productfeature_planner.apis.prd.router.find_unfinalized")
def test_resume_not_found(mock_find, client):
    """Resuming a non-resumable run_id should 404."""
    mock_find.return_value = []
    resp = client.post("/flow/prd/resume", json={"run_id": "nope"})
    assert resp.status_code == 404


@patch("crewai_productfeature_planner.apis.prd.router.resume_prd_flow")
@patch("crewai_productfeature_planner.apis.prd.router.find_unfinalized")
def test_resume_success(mock_find, mock_resume, client):
    """Resuming a valid run should return 202."""
    mock_find.return_value = [
        {
            "run_id": "abc123",
            "idea": "Dark mode",
            "iteration": 3,
            "sections": ["executive_summary"],
        }
    ]
    resp = client.post("/flow/prd/resume", json={"run_id": "abc123"})
    assert resp.status_code == 202
    body = resp.json()
    assert body["run_id"] == "abc123"
    assert body["status"] == "running"
    assert body["sections_approved"] == 1
    assert "abc123" in runs


def test_resume_already_active(client):
    """Resuming a run that is already running should 409."""
    run = FlowRun(run_id="active", flow_name="prd", status=FlowStatus.RUNNING)
    runs["active"] = run
    resp = client.post("/flow/prd/resume", json={"run_id": "active"})
    assert resp.status_code == 409


# ── GET /flow/runs ───────────────────────────────────────────


def test_list_runs_empty(client):
    """Should return empty list when no runs exist."""
    resp = client.get("/flow/runs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["runs"] == []


def test_list_runs_with_data(client):
    """Should return all in-memory runs."""
    runs["r1"] = FlowRun(run_id="r1", flow_name="prd", status=FlowStatus.RUNNING)
    runs["r2"] = FlowRun(run_id="r2", flow_name="prd", status=FlowStatus.COMPLETED)
    resp = client.get("/flow/runs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    run_ids = {r["run_id"] for r in body["runs"]}
    assert run_ids == {"r1", "r2"}
