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
    approval_selected,
    pause_requested,
    runs,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


@pytest.fixture(autouse=True)
def _mock_crew_jobs():
    """Prevent API tests from writing to real MongoDB crewJobs collection.

    Patches both the router-level imports (kickoff endpoint) and the
    service-level imports (run_prd_flow / make_approval_callback) so
    that no test in this module ever touches a real database.

    Also patches ``fail_incomplete_jobs_on_startup`` used in the
    FastAPI lifespan to prevent a real MongoDB connection on startup.
    """
    with (
        patch("crewai_productfeature_planner.apis.prd.router.create_job"),
        patch(
            "crewai_productfeature_planner.apis.prd.router.find_active_job",
            return_value=None,
        ),
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


@pytest.fixture()
def client():
    """Provide a fresh TestClient and clear stores between tests."""
    runs.clear()
    approval_events.clear()
    approval_decisions.clear()
    approval_feedback.clear()
    approval_selected.clear()
    pause_requested.clear()
    with TestClient(app) as c:
        yield c
    runs.clear()
    approval_events.clear()
    approval_decisions.clear()
    approval_feedback.clear()
    approval_selected.clear()
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
    assert body["sections_approved"] == 0
    assert body["sections_total"] == 10


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
    """Failed flow should set status to PAUSED (kept inprogress for resume)."""
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

    assert run.status == FlowStatus.PAUSED
    assert "LLM timeout" in run.error
    assert run.error.startswith("INTERNAL_ERROR:")


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


def test_run_prd_flow_billing_error():
    """BillingError should set status to PAUSED with BILLING_ERROR code."""
    from crewai_productfeature_planner.apis.prd.service import run_prd_flow
    from crewai_productfeature_planner.scripts.retry import BillingError

    runs.clear()
    run = FlowRun(run_id="test-billing", flow_name="prd")
    runs["test-billing"] = run

    with patch("crewai_productfeature_planner.flows.prd_flow.PRDFlow") as MockFlow:
        mock_instance = MagicMock()
        mock_instance.kickoff.side_effect = BillingError("insufficient_quota")
        mock_instance.state = MagicMock()
        MockFlow.return_value = mock_instance

        run_prd_flow("test-billing", "Billing idea")

    assert run.status == FlowStatus.PAUSED
    assert run.error.startswith("BILLING_ERROR:")
    assert "insufficient_quota" in run.error


def test_run_prd_flow_llm_error():
    """LLMError should set status to PAUSED with LLM_ERROR code."""
    from crewai_productfeature_planner.apis.prd.service import run_prd_flow
    from crewai_productfeature_planner.scripts.retry import LLMError

    runs.clear()
    run = FlowRun(run_id="test-llm", flow_name="prd")
    runs["test-llm"] = run

    with patch("crewai_productfeature_planner.flows.prd_flow.PRDFlow") as MockFlow:
        mock_instance = MagicMock()
        mock_instance.kickoff.side_effect = LLMError("model overloaded")
        mock_instance.state = MagicMock()
        MockFlow.return_value = mock_instance

        run_prd_flow("test-llm", "LLM idea")

    assert run.status == FlowStatus.PAUSED
    assert run.error.startswith("LLM_ERROR:")
    assert "model overloaded" in run.error


# ── make_approval_callback agent syncing ─────────────────────


def test_approval_callback_syncs_agent_state():
    """The service callback should update FlowRun with active/dropped agents."""
    from crewai_productfeature_planner.apis.prd.models import PRDDraft
    from crewai_productfeature_planner.apis.prd.service import make_approval_callback

    runs.clear()
    run = FlowRun(run_id="test-sync", flow_name="prd")
    runs["test-sync"] = run

    callback = make_approval_callback("test-sync")

    # Simulate approval in a thread (callback blocks on event.wait)
    def _approve():
        import time
        time.sleep(0.05)
        approval_decisions["test-sync"] = True
        approval_events["test-sync"].set()

    import threading as _threading
    t = _threading.Thread(target=_approve)
    t.start()

    result = callback(
        1,
        "executive_summary",
        {"openai_pm": "draft content"},
        PRDDraft.create_empty(),
        active_agents=["openai_pm"],
        dropped_agents=["gemini_pm"],
        agent_errors={"gemini_pm": "RuntimeError: model not found"},
    )
    t.join()

    assert run.active_agents == ["openai_pm"]
    assert run.dropped_agents == ["gemini_pm"]
    assert run.agent_errors == {"gemini_pm": "RuntimeError: model not found"}

    # Cleanup
    approval_events.pop("test-sync", None)
    approval_decisions.pop("test-sync", None)
    runs.clear()


# ── Global error handler ─────────────────────────────────────


def test_global_error_handler_returns_500():
    """Unhandled exceptions should return 500 with ErrorResponse envelope."""
    runs.clear()
    mock_runs = MagicMock()
    mock_runs.get.side_effect = RuntimeError("db down")
    with patch(
        "crewai_productfeature_planner.apis.prd.router.runs",
        mock_runs,
    ):
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/flow/runs/test-crash")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error_code"] == "INTERNAL_ERROR"
    assert "db down" in body["message"]
    runs.clear()


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


def test_approve_with_selected_agent(client):
    """selected_agent should be stored in approval_selected."""
    run = FlowRun(
        run_id="r6", flow_name="prd", status=FlowStatus.AWAITING_APPROVAL
    )
    run.current_section_key = "executive_summary"
    runs["r6"] = run
    event = threading.Event()
    approval_events["r6"] = event

    resp = client.post(
        "/flow/prd/approve",
        json={
            "run_id": "r6",
            "approve": True,
            "selected_agent": "gemini_pm",
        },
    )
    assert resp.status_code == 200
    assert approval_selected.get("r6") == "gemini_pm"


def test_approve_without_selected_agent(client):
    """When selected_agent is omitted, approval_selected should not be set."""
    run = FlowRun(
        run_id="r7", flow_name="prd", status=FlowStatus.AWAITING_APPROVAL
    )
    run.current_section_key = "executive_summary"
    runs["r7"] = run
    event = threading.Event()
    approval_events["r7"] = event

    resp = client.post(
        "/flow/prd/approve",
        json={"run_id": "r7", "approve": True},
    )
    assert resp.status_code == 200
    assert "r7" not in approval_selected


# ── Agent tracking in responses ──────────────────────────────


def test_approve_response_includes_active_agents(client):
    """Approve response should include active_agents, dropped_agents and agent_errors."""
    run = FlowRun(
        run_id="r-agents", flow_name="prd", status=FlowStatus.AWAITING_APPROVAL
    )
    run.current_section_key = "executive_summary"
    run.active_agents = ["openai_pm", "gemini_pm"]
    run.dropped_agents = []
    run.agent_errors = {}
    runs["r-agents"] = run
    event = threading.Event()
    approval_events["r-agents"] = event

    resp = client.post(
        "/flow/prd/approve",
        json={"run_id": "r-agents", "approve": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_agents"] == ["openai_pm", "gemini_pm"]
    assert body["dropped_agents"] == []
    assert body["agent_errors"] == {}


def test_approve_response_shows_dropped_agents(client):
    """Approve response should reflect dropped agents and their errors."""
    run = FlowRun(
        run_id="r-dropped", flow_name="prd", status=FlowStatus.AWAITING_APPROVAL
    )
    run.current_section_key = "problem_statement"
    run.active_agents = ["openai_pm"]
    run.dropped_agents = ["gemini_pm"]
    run.agent_errors = {"gemini_pm": "RuntimeError: model not found"}
    runs["r-dropped"] = run
    event = threading.Event()
    approval_events["r-dropped"] = event

    resp = client.post(
        "/flow/prd/approve",
        json={"run_id": "r-dropped", "approve": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_agents"] == ["openai_pm"]
    assert body["dropped_agents"] == ["gemini_pm"]
    assert body["agent_errors"] == {"gemini_pm": "RuntimeError: model not found"}


def test_run_status_includes_agent_tracking(client):
    """GET /flow/runs/{run_id} should include agent tracking fields."""
    run = FlowRun(run_id="r-status-agents", flow_name="prd")
    run.active_agents = ["openai_pm"]
    run.dropped_agents = ["gemini_pm"]
    run.agent_errors = {"gemini_pm": "RuntimeError: boom"}
    runs["r-status-agents"] = run

    resp = client.get("/flow/runs/r-status-agents")
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_agents"] == ["openai_pm"]
    assert body["dropped_agents"] == ["gemini_pm"]
    assert body["agent_errors"] == {"gemini_pm": "RuntimeError: boom"}


def test_run_status_empty_agents_by_default(client):
    """A new run should have empty agent lists until the flow starts."""
    with patch("crewai_productfeature_planner.apis.prd.router.run_prd_flow"):
        resp = client.post(
            "/flow/prd/kickoff",
            json={"idea": "Agent tracking test"},
        )
    run_id = resp.json()["run_id"]
    status_resp = client.get(f"/flow/runs/{run_id}")
    body = status_resp.json()
    assert body["active_agents"] == []
    assert body["dropped_agents"] == []
    assert body["agent_errors"] == {}
    assert body["original_idea"] == ""
    assert body["idea_refined"] is False


def test_pause_response_includes_agents(client):
    """Pause response should include agent tracking fields."""
    run = FlowRun(
        run_id="r-pause-agents", flow_name="prd", status=FlowStatus.AWAITING_APPROVAL
    )
    run.current_section_key = "executive_summary"
    run.active_agents = ["openai_pm"]
    run.dropped_agents = ["gemini_pm"]
    run.agent_errors = {"gemini_pm": "RuntimeError: timeout"}
    runs["r-pause-agents"] = run
    event = threading.Event()
    approval_events["r-pause-agents"] = event

    resp = client.post("/flow/prd/pause", json={"run_id": "r-pause-agents"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_agents"] == ["openai_pm"]
    assert body["dropped_agents"] == ["gemini_pm"]
    assert body["agent_errors"] == {"gemini_pm": "RuntimeError: timeout"}


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
    assert body["sections_approved"] == 0
    assert body["sections_total"] == 10
    assert body["is_final_section"] is False
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


@patch("crewai_productfeature_planner.mongodb.find_unfinalized")
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


@patch("crewai_productfeature_planner.mongodb.find_unfinalized")
def test_list_resumable_empty(mock_find, client):
    """Should return empty list when no resumable runs."""
    mock_find.return_value = []
    resp = client.get("/flow/prd/resumable")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["runs"] == []


# ── POST /flow/prd/resume ────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.find_unfinalized")
def test_resume_not_found(mock_find, client):
    """Resuming a non-resumable run_id should 404."""
    mock_find.return_value = []
    resp = client.post("/flow/prd/resume", json={"run_id": "nope"})
    assert resp.status_code == 404


@patch("crewai_productfeature_planner.apis.prd.router.resume_prd_flow")
@patch("crewai_productfeature_planner.mongodb.find_unfinalized")
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
    assert body["sections_total"] == 10
    assert body["next_section"] == "problem_statement"
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


# ── ErrorResponse model ──────────────────────────────────────


def test_error_response_model():
    """ErrorResponse should serialize with required and optional fields."""
    from crewai_productfeature_planner.apis.prd.models import ErrorResponse

    err = ErrorResponse(
        error_code="LLM_ERROR",
        message="model overloaded",
        run_id="abc123",
        detail="LLMError: model overloaded",
    )
    data = err.model_dump()
    assert data["error_code"] == "LLM_ERROR"
    assert data["message"] == "model overloaded"
    assert data["run_id"] == "abc123"
    assert data["detail"] == "LLMError: model overloaded"


def test_error_response_minimal():
    """ErrorResponse should work with only required fields."""
    from crewai_productfeature_planner.apis.prd.models import ErrorResponse

    err = ErrorResponse(error_code="INTERNAL_ERROR", message="boom")
    data = err.model_dump()
    assert data["error_code"] == "INTERNAL_ERROR"
    assert data["run_id"] is None
    assert data["detail"] is None


def test_openapi_schema_includes_error_response(client):
    """The generated OpenAPI schema should include the ErrorResponse schema."""
    resp = client.get("/openapi.json")
    schema = resp.json()
    assert "ErrorResponse" in schema["components"]["schemas"]
    err_schema = schema["components"]["schemas"]["ErrorResponse"]
    assert "error_code" in err_schema["properties"]
    assert "message" in err_schema["properties"]


def test_openapi_schema_includes_agent_tracking_fields(client):
    """PRDRunStatusResponse & PRDActionResponse should have agent tracking fields."""
    resp = client.get("/openapi.json")
    schema = resp.json()
    schemas = schema["components"]["schemas"]

    # PRDRunStatusResponse
    run_status = schemas["PRDRunStatusResponse"]
    assert "active_agents" in run_status["properties"]
    assert "dropped_agents" in run_status["properties"]
    assert "agent_errors" in run_status["properties"]
    assert "original_idea" in run_status["properties"]
    assert "idea_refined" in run_status["properties"]

    # PRDActionResponse
    action_resp = schemas["PRDActionResponse"]
    assert "active_agents" in action_resp["properties"]
    assert "dropped_agents" in action_resp["properties"]
    assert "agent_errors" in action_resp["properties"]

    # PRDSectionDetail should have agent_results and selected_agent
    section_detail = schemas["PRDSectionDetail"]
    assert "agent_results" in section_detail["properties"]
    assert "selected_agent" in section_detail["properties"]


# ── Single active job guard ──────────────────────────────────


def test_kickoff_rejects_when_active_job_exists(client):
    """Kickoff should return 409 when an active job already exists."""
    active_job = {"job_id": "existing-123", "status": "running"}
    with patch(
        "crewai_productfeature_planner.apis.prd.router.find_active_job",
        return_value=active_job,
    ):
        resp = client.post(
            "/flow/prd/kickoff",
            json={"idea": "Another idea"},
        )
    assert resp.status_code == 409
    assert "existing-123" in resp.json()["detail"]
    assert "already active" in resp.json()["detail"]


def test_endpoints_document_500_503(client):
    """All flow endpoints should document 500 and 503 error responses."""
    resp = client.get("/openapi.json")
    schema = resp.json()
    flow_paths = [p for p in schema["paths"] if p.startswith("/flow/")]
    for path in flow_paths:
        for method, spec in schema["paths"][path].items():
            if method in ("get", "post", "put", "patch", "delete"):
                responses = spec.get("responses", {})
                assert "500" in responses, f"{method.upper()} {path} missing 500"
                assert "503" in responses, f"{method.upper()} {path} missing 503"


# ── auto_approve mode ────────────────────────────────────────


def test_kickoff_auto_approve_returns_202(client):
    """Kickoff with auto_approve=true should return 202 with auto-approve message."""
    with patch("crewai_productfeature_planner.apis.prd.router.run_prd_flow"):
        resp = client.post(
            "/flow/prd/kickoff",
            json={"idea": "Dark mode", "auto_approve": True},
        )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "pending"
    assert "auto-approve" in body["message"]
    # Should NOT mention /approve endpoint
    assert "/flow/prd/approve" not in body["message"]


def test_kickoff_no_auto_approve_mentions_approve(client):
    """Kickoff without auto_approve should mention /approve in message."""
    with patch("crewai_productfeature_planner.apis.prd.router.run_prd_flow"):
        resp = client.post(
            "/flow/prd/kickoff",
            json={"idea": "Dark mode"},
        )
    body = resp.json()
    assert "/flow/prd/approve" in body["message"]


def test_kickoff_auto_approve_skips_callback():
    """run_prd_flow with auto_approve=True should not set approval_callback."""
    from crewai_productfeature_planner.apis.prd.service import run_prd_flow

    runs.clear()
    run = FlowRun(run_id="auto-ok", flow_name="prd")
    runs["auto-ok"] = run

    with patch("crewai_productfeature_planner.flows.prd_flow.PRDFlow") as MockFlow:
        mock_instance = MagicMock()
        mock_instance.approval_callback = None  # explicit default
        mock_instance.kickoff.return_value = "# PRD done"
        mock_instance.state = MagicMock()
        MockFlow.return_value = mock_instance

        run_prd_flow("auto-ok", "Idea", auto_approve=True)

    # approval_callback should NOT have been set
    assert mock_instance.approval_callback is None


def test_kickoff_manual_approve_sets_callback():
    """run_prd_flow with auto_approve=False should set approval_callback."""
    from crewai_productfeature_planner.apis.prd.service import run_prd_flow

    runs.clear()
    run = FlowRun(run_id="manual-ok", flow_name="prd")
    runs["manual-ok"] = run

    with patch("crewai_productfeature_planner.flows.prd_flow.PRDFlow") as MockFlow:
        mock_instance = MagicMock()
        mock_instance.approval_callback = None  # explicit default
        mock_instance.kickoff.return_value = "# PRD done"
        mock_instance.state = MagicMock()
        MockFlow.return_value = mock_instance

        run_prd_flow("manual-ok", "Idea", auto_approve=False)

    # approval_callback should have been set to a callable
    assert mock_instance.approval_callback is not None
    assert callable(mock_instance.approval_callback)


@patch("crewai_productfeature_planner.apis.prd.router.resume_prd_flow")
@patch("crewai_productfeature_planner.mongodb.find_unfinalized")
def test_resume_auto_approve_returns_202(mock_find, mock_resume, client):
    """Resume with auto_approve=true should return 202 with auto-approve message."""
    mock_find.return_value = [
        {
            "run_id": "abc123",
            "idea": "Dark mode",
            "iteration": 3,
            "sections": ["executive_summary"],
        }
    ]
    resp = client.post(
        "/flow/prd/resume",
        json={"run_id": "abc123", "auto_approve": True},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "auto-approve" in body["message"]
    # The service should have been called with auto_approve=True
    mock_resume.assert_called_once_with("abc123", True)


@patch("crewai_productfeature_planner.apis.prd.router.resume_prd_flow")
@patch("crewai_productfeature_planner.mongodb.find_unfinalized")
def test_resume_no_auto_approve_default(mock_find, mock_resume, client):
    """Resume without auto_approve defaults to False."""
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
    # The service should have been called with auto_approve=False
    mock_resume.assert_called_once_with("abc123", False)


def test_resume_auto_approve_skips_callback():
    """resume_prd_flow with auto_approve=True should not set approval_callback."""
    from crewai_productfeature_planner.apis.prd.service import resume_prd_flow

    runs.clear()
    run = FlowRun(run_id="resume-auto", flow_name="prd")
    runs["resume-auto"] = run

    with (
        patch("crewai_productfeature_planner.flows.prd_flow.PRDFlow") as MockFlow,
        patch(
            "crewai_productfeature_planner.apis.prd.service.restore_prd_state"
        ) as mock_restore,
    ):
        from crewai_productfeature_planner.apis.prd.models import (
            ExecutiveSummaryDraft,
            PRDDraft,
        )
        mock_restore.return_value = (
            "idea",
            PRDDraft.create_empty(),
            ExecutiveSummaryDraft(),
            "",
            [],
        )
        mock_instance = MagicMock()
        mock_instance.approval_callback = None  # explicit default
        mock_instance.kickoff.return_value = "# PRD"
        mock_instance.state = MagicMock()
        MockFlow.return_value = mock_instance

        resume_prd_flow("resume-auto", auto_approve=True)

    assert mock_instance.approval_callback is None


# ── New fields: FlowRun / status-response ────────────────────


def test_run_status_includes_confluence_url(client):
    """GET /flow/runs/{run_id} should expose confluence_url."""
    run = FlowRun(run_id="r-conf", flow_name="prd")
    run.confluence_url = "https://wiki.example.com/pages/12345"
    runs["r-conf"] = run

    resp = client.get("/flow/runs/r-conf")
    assert resp.status_code == 200
    assert resp.json()["confluence_url"] == "https://wiki.example.com/pages/12345"


def test_run_status_includes_jira_output(client):
    """GET /flow/runs/{run_id} should expose jira_output."""
    run = FlowRun(run_id="r-jira", flow_name="prd")
    run.jira_output = "Created PROJ-101, PROJ-102"
    runs["r-jira"] = run

    resp = client.get("/flow/runs/r-jira")
    assert resp.status_code == 200
    assert resp.json()["jira_output"] == "Created PROJ-101, PROJ-102"


def test_run_status_includes_output_file(client):
    """GET /flow/runs/{run_id} should expose output_file."""
    run = FlowRun(run_id="r-out", flow_name="prd")
    run.output_file = "output/prds/prd_v1_20260223.md"
    runs["r-out"] = run

    resp = client.get("/flow/runs/r-out")
    assert resp.status_code == 200
    assert resp.json()["output_file"] == "output/prds/prd_v1_20260223.md"


def test_run_status_includes_finalized_idea(client):
    """GET /flow/runs/{run_id} should expose finalized_idea."""
    run = FlowRun(run_id="r-fin", flow_name="prd")
    run.finalized_idea = "A refined executive summary of the feature"
    runs["r-fin"] = run

    resp = client.get("/flow/runs/r-fin")
    assert resp.status_code == 200
    assert resp.json()["finalized_idea"] == "A refined executive summary of the feature"


def test_run_status_includes_requirements_breakdown(client):
    """GET /flow/runs/{run_id} should expose requirements_breakdown."""
    run = FlowRun(run_id="r-req", flow_name="prd")
    run.requirements_breakdown = "## Requirements\n- FR1: User login"
    runs["r-req"] = run

    resp = client.get("/flow/runs/r-req")
    assert resp.status_code == 200
    assert "FR1: User login" in resp.json()["requirements_breakdown"]


def test_run_status_includes_executive_summary(client):
    """GET /flow/runs/{run_id} should expose executive_summary with iterations."""
    from crewai_productfeature_planner.apis.prd.models import (
        ExecutiveSummaryDraft,
        ExecutiveSummaryIteration,
    )

    run = FlowRun(run_id="r-exec", flow_name="prd")
    run.executive_summary = ExecutiveSummaryDraft(
        iterations=[
            ExecutiveSummaryIteration(
                content="First draft of exec summary",
                iteration=1,
                critique="Needs more detail",
                updated_date="2026-02-23T10:00:00Z",
            ),
            ExecutiveSummaryIteration(
                content="Refined exec summary with more detail",
                iteration=2,
                critique=None,
                updated_date="2026-02-23T10:05:00Z",
            ),
        ],
        is_approved=True,
    )
    runs["r-exec"] = run

    resp = client.get("/flow/runs/r-exec")
    assert resp.status_code == 200
    body = resp.json()
    exec_summary = body["executive_summary"]
    assert exec_summary["is_approved"] is True
    assert len(exec_summary["iterations"]) == 2
    assert exec_summary["iterations"][0]["content"] == "First draft of exec summary"
    assert exec_summary["iterations"][1]["iteration"] == 2


def test_run_status_new_fields_default_empty(client):
    """New fields should default to empty values on a fresh FlowRun."""
    with patch("crewai_productfeature_planner.apis.prd.router.run_prd_flow"):
        resp = client.post(
            "/flow/prd/kickoff",
            json={"idea": "New fields test"},
        )
    run_id = resp.json()["run_id"]
    status_resp = client.get(f"/flow/runs/{run_id}")
    body = status_resp.json()
    assert body["confluence_url"] == ""
    assert body["jira_output"] == ""
    assert body["output_file"] == ""
    assert body["finalized_idea"] == ""
    assert body["requirements_breakdown"] == ""
    assert body["executive_summary"]["iterations"] == []
    assert body["executive_summary"]["is_approved"] is False


# ── _sync_flow_state_to_run ──────────────────────────────────


def test_sync_flow_state_copies_all_fields():
    """_sync_flow_state_to_run should copy every new state field to FlowRun."""
    from crewai_productfeature_planner.apis.prd.models import (
        ExecutiveSummaryDraft,
        ExecutiveSummaryIteration,
    )
    from crewai_productfeature_planner.apis.prd.service import _sync_flow_state_to_run

    runs.clear()
    run = FlowRun(run_id="sync-test", flow_name="prd")
    runs["sync-test"] = run

    mock_flow = MagicMock()
    mock_flow.state.draft = MagicMock()
    mock_flow.state.current_section_key = "user_personas"
    mock_flow.state.iteration = 5
    mock_flow.state.active_agents = ["gemini_pm"]
    mock_flow.state.dropped_agents = ["openai_pm"]
    mock_flow.state.agent_errors = {"openai_pm": "timeout"}
    mock_flow.state.original_idea = "original idea text"
    mock_flow.state.idea_refined = True
    mock_flow.state.finalized_idea = "refined executive summary"
    mock_flow.state.requirements_breakdown = "structured requirements"
    mock_flow.state.executive_summary = ExecutiveSummaryDraft(
        iterations=[ExecutiveSummaryIteration(content="exec", iteration=1)],
    )
    mock_flow.state.confluence_url = "https://wiki.test.com/page/1"
    mock_flow.state.jira_output = "PROJ-1"
    mock_flow.state.final_prd = ""

    _sync_flow_state_to_run("sync-test", mock_flow)

    assert run.current_section_key == "user_personas"
    assert run.iteration == 5
    assert run.active_agents == ["gemini_pm"]
    assert run.dropped_agents == ["openai_pm"]
    assert run.agent_errors == {"openai_pm": "timeout"}
    assert run.original_idea == "original idea text"
    assert run.idea_refined is True
    assert run.finalized_idea == "refined executive summary"
    assert run.requirements_breakdown == "structured requirements"
    assert run.confluence_url == "https://wiki.test.com/page/1"
    assert run.jira_output == "PROJ-1"
    assert run.executive_summary.iterations[0].content == "exec"
    runs.clear()


def test_sync_flow_state_noop_missing_run():
    """_sync_flow_state_to_run should silently skip if run_id not found."""
    from crewai_productfeature_planner.apis.prd.service import _sync_flow_state_to_run

    runs.clear()
    _sync_flow_state_to_run("nonexistent", MagicMock())


def test_sync_flow_state_queries_output_file_from_db():
    """When final_prd is non-empty, _sync should query MongoDB for output_file."""
    from crewai_productfeature_planner.apis.prd.service import _sync_flow_state_to_run

    runs.clear()
    run = FlowRun(run_id="sync-out", flow_name="prd")
    runs["sync-out"] = run

    mock_flow = MagicMock()
    mock_flow.state.final_prd = "# Some PRD content"
    mock_flow.state.confluence_url = ""
    mock_flow.state.jira_output = ""
    mock_flow.state.finalized_idea = ""
    mock_flow.state.requirements_breakdown = ""

    with patch(
        "crewai_productfeature_planner.mongodb.get_output_file",
        return_value="output/prds/prd_v2_test.md",
    ) as mock_get:
        _sync_flow_state_to_run("sync-out", mock_flow)

    mock_get.assert_called_once_with("sync-out")
    assert run.output_file == "output/prds/prd_v2_test.md"
    runs.clear()


# ── run_prd_flow state sync ──────────────────────────────────


def test_run_prd_flow_syncs_state_on_completion():
    """run_prd_flow should sync flow state after successful completion."""
    from crewai_productfeature_planner.apis.prd.service import run_prd_flow

    runs.clear()
    run = FlowRun(run_id="sync-ok", flow_name="prd")
    runs["sync-ok"] = run

    with patch("crewai_productfeature_planner.flows.prd_flow.PRDFlow") as MockFlow:
        mock_instance = MagicMock()
        mock_instance.kickoff.return_value = "# Done"
        mock_instance.state.confluence_url = "https://wiki.test.com/done"
        mock_instance.state.jira_output = "PROJ-99"
        mock_instance.state.finalized_idea = "final exec summary"
        mock_instance.state.requirements_breakdown = "FR1, FR2"
        mock_instance.state.final_prd = ""
        mock_instance.state.is_ready = True
        MockFlow.return_value = mock_instance

        run_prd_flow("sync-ok", "Test idea")

    assert run.confluence_url == "https://wiki.test.com/done"
    assert run.jira_output == "PROJ-99"
    assert run.finalized_idea == "final exec summary"
    assert run.requirements_breakdown == "FR1, FR2"
    runs.clear()


def test_run_prd_flow_syncs_state_on_pause():
    """run_prd_flow should sync flow state even when PauseRequested."""
    from crewai_productfeature_planner.apis.prd.service import run_prd_flow
    from crewai_productfeature_planner.flows.prd_flow import PauseRequested

    runs.clear()
    run = FlowRun(run_id="sync-pause", flow_name="prd")
    runs["sync-pause"] = run

    with patch("crewai_productfeature_planner.flows.prd_flow.PRDFlow") as MockFlow:
        mock_instance = MagicMock()
        mock_instance.kickoff.side_effect = PauseRequested()
        mock_instance.state.requirements_breakdown = "partial reqs"
        mock_instance.state.final_prd = ""
        MockFlow.return_value = mock_instance

        run_prd_flow("sync-pause", "Test idea")

    assert run.status == FlowStatus.PAUSED
    assert run.requirements_breakdown == "partial reqs"
    runs.clear()


def test_run_prd_flow_syncs_state_on_error():
    """run_prd_flow should sync flow state even on unexpected exceptions."""
    from crewai_productfeature_planner.apis.prd.service import run_prd_flow

    runs.clear()
    run = FlowRun(run_id="sync-err", flow_name="prd")
    runs["sync-err"] = run

    with patch("crewai_productfeature_planner.flows.prd_flow.PRDFlow") as MockFlow:
        mock_instance = MagicMock()
        mock_instance.kickoff.side_effect = RuntimeError("boom")
        mock_instance.state.confluence_url = "https://wiki.test.com/partial"
        mock_instance.state.final_prd = ""
        MockFlow.return_value = mock_instance

        run_prd_flow("sync-err", "Test idea")

    assert run.status == FlowStatus.PAUSED
    assert "INTERNAL_ERROR" in run.error
    assert run.confluence_url == "https://wiki.test.com/partial"
    runs.clear()


# ── Approval callback syncs new kwargs ───────────────────────


def test_approval_callback_syncs_new_kwargs():
    """The approval callback should sync finalized_idea, requirements_breakdown, executive_summary."""
    from crewai_productfeature_planner.apis.prd.models import (
        ExecutiveSummaryDraft,
        ExecutiveSummaryIteration,
        PRDDraft,
    )
    from crewai_productfeature_planner.apis.prd.service import make_approval_callback

    runs.clear()
    run = FlowRun(run_id="cb-sync", flow_name="prd")
    runs["cb-sync"] = run

    callback = make_approval_callback("cb-sync")

    exec_summary = ExecutiveSummaryDraft(
        iterations=[ExecutiveSummaryIteration(content="exec content", iteration=1)],
    )

    def _approve():
        import time
        time.sleep(0.05)
        approval_decisions["cb-sync"] = True
        approval_events["cb-sync"].set()

    import threading as _threading
    t = _threading.Thread(target=_approve)
    t.start()

    callback(
        1,
        "executive_summary",
        {"gemini_pm": "draft"},
        PRDDraft.create_empty(),
        active_agents=["gemini_pm"],
        finalized_idea="refined idea",
        requirements_breakdown="## Requirements list",
        executive_summary=exec_summary,
    )
    t.join()

    assert run.finalized_idea == "refined idea"
    assert run.requirements_breakdown == "## Requirements list"
    assert run.executive_summary.iterations[0].content == "exec content"

    approval_events.pop("cb-sync", None)
    approval_decisions.pop("cb-sync", None)
    runs.clear()


def test_approval_callback_preserves_existing_when_kwargs_absent():
    """When new kwargs are not passed, existing FlowRun values should be kept."""
    from crewai_productfeature_planner.apis.prd.models import PRDDraft
    from crewai_productfeature_planner.apis.prd.service import make_approval_callback

    runs.clear()
    run = FlowRun(run_id="cb-keep", flow_name="prd")
    run.finalized_idea = "already set"
    run.requirements_breakdown = "existing reqs"
    runs["cb-keep"] = run

    callback = make_approval_callback("cb-keep")

    def _approve():
        import time
        time.sleep(0.05)
        approval_decisions["cb-keep"] = True
        approval_events["cb-keep"].set()

    import threading as _threading
    t = _threading.Thread(target=_approve)
    t.start()

    # Call without the new kwargs
    callback(
        1,
        "problem_statement",
        {"gemini_pm": "draft"},
        PRDDraft.create_empty(),
        active_agents=["gemini_pm"],
    )
    t.join()

    # Existing values should be preserved
    assert run.finalized_idea == "already set"
    assert run.requirements_breakdown == "existing reqs"

    approval_events.pop("cb-keep", None)
    approval_decisions.pop("cb-keep", None)
    runs.clear()


# ── Resumable runs iteration counts ─────────────────────────


@patch("crewai_productfeature_planner.mongodb.find_unfinalized")
def test_resumable_runs_include_iteration_counts(mock_find, client):
    """GET /flow/prd/resumable should include exec_summary and req_breakdown iteration counts."""
    mock_find.return_value = [
        {
            "run_id": "res-1",
            "idea": "Dark mode",
            "iteration": 3,
            "sections": ["executive_summary", "problem_statement"],
            "exec_summary_iterations": 5,
            "req_breakdown_iterations": 2,
            "created_at": "2026-02-23T12:00:00Z",
        },
    ]
    resp = client.get("/flow/prd/resumable")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    run_data = body["runs"][0]
    assert run_data["exec_summary_iterations"] == 5
    assert run_data["req_breakdown_iterations"] == 2


@patch("crewai_productfeature_planner.mongodb.find_unfinalized")
def test_resumable_runs_default_zero_iterations(mock_find, client):
    """Missing exec/req iteration counts should default to 0."""
    mock_find.return_value = [
        {
            "run_id": "res-2",
            "idea": "Light mode",
            "iteration": 1,
            "sections": [],
            "created_at": "2026-02-23T12:00:00Z",
        },
    ]
    resp = client.get("/flow/prd/resumable")
    body = resp.json()
    run_data = body["runs"][0]
    assert run_data["exec_summary_iterations"] == 0
    assert run_data["req_breakdown_iterations"] == 0


# ── restore_prd_state full 5-tuple ──────────────────────────


def test_restore_prd_state_returns_five_tuple():
    """restore_prd_state should return (idea, draft, exec_summary, requirements, breakdown_history)."""
    from crewai_productfeature_planner.apis.prd.service import restore_prd_state

    with (
        patch("crewai_productfeature_planner.mongodb.find_unfinalized") as mock_unf,
        patch("crewai_productfeature_planner.mongodb.get_run_documents") as mock_docs,
    ):
        mock_unf.return_value = [{"run_id": "r1", "idea": "Test idea"}]
        mock_docs.return_value = [{
            "section": {
                "executive_summary": [{"content": "ES content", "iteration": 1}],
                "problem_statement": [{"content": "PS content", "iteration": 1}],
            },
            "executive_summary": [
                {"content": "ES iteration 1", "iteration": 1, "critique": "needs more"},
                {"content": "ES iteration 2", "iteration": 2, "critique": None},
            ],
            "requirements_breakdown": [
                {"content": "Req v1", "iteration": 1, "critique": "ok"},
                {"content": "Req v2", "iteration": 2, "critique": "good"},
            ],
        }]

        result = restore_prd_state("r1")

    assert len(result) == 5
    idea, draft, exec_summary, requirements, breakdown_history = result
    assert idea == "Test idea"
    assert draft.get_section("executive_summary").content == "ES content"
    assert draft.get_section("problem_statement").content == "PS content"
    assert len(exec_summary.iterations) == 2
    assert exec_summary.iterations[0].content == "ES iteration 1"
    assert exec_summary.iterations[1].critique is None
    assert exec_summary.is_approved is True
    assert requirements == "Req v2"
    assert len(breakdown_history) == 2
    assert breakdown_history[0]["requirements"] == "Req v1"
    assert breakdown_history[1]["requirements"] == "Req v2"


def test_restore_prd_state_no_exec_summary():
    """restore_prd_state should handle missing executive_summary gracefully."""
    from crewai_productfeature_planner.apis.prd.service import restore_prd_state

    with (
        patch("crewai_productfeature_planner.mongodb.find_unfinalized") as mock_unf,
        patch("crewai_productfeature_planner.mongodb.get_run_documents") as mock_docs,
    ):
        mock_unf.return_value = [{"run_id": "r2", "idea": "Idea"}]
        mock_docs.return_value = [{"section": {}}]

        idea, draft, exec_summary, requirements, breakdown_history = restore_prd_state("r2")

    assert idea == "Idea"
    assert len(exec_summary.iterations) == 0
    assert exec_summary.is_approved is False
    assert requirements == ""
    assert breakdown_history == []


def test_restore_prd_state_reinitialises_missing_section():
    """restore_prd_state should reinitialise when 'section' field is missing."""
    from crewai_productfeature_planner.apis.prd.service import restore_prd_state

    with (
        patch("crewai_productfeature_planner.mongodb.find_unfinalized") as mock_unf,
        patch("crewai_productfeature_planner.mongodb.get_run_documents") as mock_docs,
        patch("crewai_productfeature_planner.mongodb.ensure_section_field") as mock_ensure,
    ):
        mock_unf.return_value = [{"run_id": "r3", "idea": "Idea"}]
        mock_docs.return_value = [{"foo": "bar"}]

        restore_prd_state("r3")

    mock_ensure.assert_called_once_with("r3")


def test_restore_prd_state_not_found():
    """restore_prd_state should raise ValueError when run_id is not in unfinalized."""
    from crewai_productfeature_planner.apis.prd.service import restore_prd_state

    with patch("crewai_productfeature_planner.mongodb.find_unfinalized") as mock_unf:
        mock_unf.return_value = []

        with pytest.raises(ValueError, match="not found"):
            restore_prd_state("nonexistent")


# ── Job detail with new fields ───────────────────────────────


def test_job_detail_includes_output_file_and_confluence(client):
    """GET /flow/jobs/{job_id} should include output_file and confluence_url."""
    with patch("crewai_productfeature_planner.apis.prd.router.find_job") as mock_find:
        mock_find.return_value = {
            "job_id": "j1",
            "flow_name": "prd",
            "idea": "test",
            "status": "completed",
            "output_file": "output/prds/prd_v1.md",
            "confluence_url": "https://wiki.test.com/page/1",
        }
        resp = client.get("/flow/jobs/j1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["output_file"] == "output/prds/prd_v1.md"
    assert body["confluence_url"] == "https://wiki.test.com/page/1"


def test_job_detail_null_for_missing_output_fields(client):
    """GET /flow/jobs/{job_id} should return null for missing output fields."""
    with patch("crewai_productfeature_planner.apis.prd.router.find_job") as mock_find:
        mock_find.return_value = {
            "job_id": "j2",
            "flow_name": "prd",
            "idea": "test",
            "status": "running",
        }
        resp = client.get("/flow/jobs/j2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["output_file"] is None
    assert body["confluence_url"] is None


# ── Resume sets restored exec/req state on flow ─────────────


def test_resume_prd_flow_restores_full_state():
    """resume_prd_flow should restore exec_summary and requirements from 5-tuple."""
    from crewai_productfeature_planner.apis.prd.models import (
        ExecutiveSummaryDraft,
        ExecutiveSummaryIteration,
        PRDDraft,
    )
    from crewai_productfeature_planner.apis.prd.service import resume_prd_flow

    runs.clear()
    run = FlowRun(run_id="resume-full", flow_name="prd")
    runs["resume-full"] = run

    exec_summary = ExecutiveSummaryDraft(
        iterations=[ExecutiveSummaryIteration(content="exec v1", iteration=1)],
        is_approved=True,
    )

    with (
        patch("crewai_productfeature_planner.flows.prd_flow.PRDFlow") as MockFlow,
        patch(
            "crewai_productfeature_planner.apis.prd.service.restore_prd_state"
        ) as mock_restore,
    ):
        draft = PRDDraft.create_empty()
        mock_restore.return_value = (
            "idea",
            draft,
            exec_summary,
            "structured requirements",
            [{"iteration": 1, "requirements": "req v1"}],
        )
        mock_instance = MagicMock()
        mock_instance.approval_callback = None
        mock_instance.kickoff.return_value = "# PRD"
        mock_instance.state = MagicMock()
        mock_instance.state.final_prd = ""
        mock_instance.state.is_ready = True
        MockFlow.return_value = mock_instance

        resume_prd_flow("resume-full", auto_approve=True)

    # Verify the flow was set up with the restored state
    assert mock_instance.state.executive_summary == exec_summary
    assert mock_instance.state.requirements_breakdown == "structured requirements"
    assert mock_instance.state.requirements_broken_down is True
    assert mock_instance.state.finalized_idea == "exec v1"
    assert mock_instance.state.idea_refined is True
    runs.clear()


# ── Lifespan smoke test ─────────────────────────────────────


def test_lifespan_startup_recovery(client):
    """The lifespan runs startup recovery; the app should start without errors."""
    resp = client.get("/health")
    assert resp.status_code == 200


# ── OpenAPI schema includes new fields ───────────────────────


def test_openapi_schema_has_prd_status_new_fields(client):
    """OpenAPI schema should document the new fields on PRDRunStatusResponse."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    status_props = schema["components"]["schemas"]["PRDRunStatusResponse"]["properties"]
    for field in (
        "confluence_url", "jira_output", "output_file",
        "finalized_idea", "requirements_breakdown", "executive_summary",
    ):
        assert field in status_props, f"Missing {field} in PRDRunStatusResponse schema"


def test_openapi_schema_has_resumable_new_fields(client):
    """OpenAPI schema should document exec/req iteration counts on PRDResumableRun."""
    resp = client.get("/openapi.json")
    schema = resp.json()
    props = schema["components"]["schemas"]["PRDResumableRun"]["properties"]
    assert "exec_summary_iterations" in props
    assert "req_breakdown_iterations" in props


def test_openapi_schema_has_job_detail_new_fields(client):
    """OpenAPI schema should document output_file/confluence_url on JobDetail."""
    resp = client.get("/openapi.json")
    schema = resp.json()
    props = schema["components"]["schemas"]["JobDetail"]["properties"]
    assert "output_file" in props
    assert "confluence_url" in props
