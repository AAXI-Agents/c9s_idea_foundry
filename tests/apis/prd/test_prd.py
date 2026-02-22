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
    """Prevent API tests from writing to real MongoDB crewJobs collection."""
    with (
        patch("crewai_productfeature_planner.apis.prd.router.create_job"),
        patch(
            "crewai_productfeature_planner.apis.prd.router.find_active_job",
            return_value=None,
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
    assert body["sections_total"] == 16


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
    """Failed flow should set status to FAILED with INTERNAL_ERROR code."""
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
    assert body["sections_total"] == 16
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
    assert body["sections_total"] == 16
    assert body["next_section"] == "why_now"
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
