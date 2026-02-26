"""FastAPI application for triggering CrewAI flows via HTTP.

API convention:
    POST /flow/{flow_name}/kickoff  — start a flow
    POST /flow/{flow_name}/approve  — approve current iteration
    GET  /flow/runs/{run_id}        — check status

Each flow runs asynchronously; the HTTP response returns immediately.
User approval is handled via a per-run threading Event that the flow
blocks on between iterations.

Start the server:
    uv run start_api          # localhost:8000
    uv run start_api --ngrok  # localhost:8000 + ngrok tunnel

Subpackages:
    - ``health``  — liveness / readiness probes
    - ``prd``     — PRD generation flow endpoints
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from crewai_productfeature_planner.apis.health.router import router as health_router
from crewai_productfeature_planner.apis.prd.router import router as prd_router
from crewai_productfeature_planner.apis.shared import FlowRun, FlowStatus  # noqa: F401 (re-export)
from crewai_productfeature_planner.apis.slack.events_router import router as slack_events_router
from crewai_productfeature_planner.apis.slack.oauth_router import router as slack_oauth_router
from crewai_productfeature_planner.apis.slack.router import router as slack_router
from crewai_productfeature_planner.mongodb.crew_jobs import fail_incomplete_jobs_on_startup
from crewai_productfeature_planner.scripts.logging_config import get_logger

_logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(application: FastAPI):
    """Startup / shutdown lifecycle hook.

    Runs the same recovery tasks as the CLI on startup:
    1. Kill stale crew processes from a previous server crash.
    2. Mark incomplete crew-jobs as failed.
    3. Generate missing markdown outputs for completed ideas.
    4. Publish unpublished PRDs to Confluence (when credentials are set).
    """
    # 1. Kill stale processes
    try:
        from crewai_productfeature_planner.components.startup import _kill_stale_crew_processes
        killed = _kill_stale_crew_processes()
        if killed:
            _logger.info("Startup recovery: killed %d stale process(es)", killed)
    except Exception as exc:
        _logger.warning("Startup recovery (kill stale processes) failed: %s", exc)

    # 2. Fail incomplete jobs
    try:
        count = fail_incomplete_jobs_on_startup()
        if count:
            _logger.info("Startup recovery: %d incomplete job(s) marked as failed", count)
    except Exception as exc:
        _logger.warning("Startup recovery (fail incomplete jobs) failed: %s", exc)

    # 3. Generate missing output files
    try:
        from crewai_productfeature_planner.components.startup import _generate_missing_outputs
        generated = _generate_missing_outputs()
        if generated:
            _logger.info("Startup recovery: generated %d missing output file(s)", generated)
    except Exception as exc:
        _logger.warning("Startup recovery (generate missing outputs) failed: %s", exc)

    # 4. Startup pipeline: review markdown PRDs and publish to Confluence
    #    Uses the orchestrator stage pattern for structured execution.
    try:
        from crewai_productfeature_planner.orchestrator.stages import (
            build_startup_pipeline,
        )
        startup_pipeline = build_startup_pipeline()
        startup_pipeline.run_pipeline()
        if startup_pipeline.completed:
            _logger.info(
                "Startup pipeline: completed stage(s) %s",
                startup_pipeline.completed,
            )
        if startup_pipeline.skipped:
            _logger.info(
                "Startup pipeline: skipped stage(s) %s",
                startup_pipeline.skipped,
            )
    except Exception as exc:
        _logger.warning("Startup pipeline (markdown review) failed: %s", exc)

    # 5. Autonomous delivery: CrewAI crew-based Confluence + Jira pipeline
    #    Runs in a background thread so the server starts accepting requests
    #    immediately while the delivery agents work autonomously.
    try:
        import threading
        from crewai_productfeature_planner.components.startup import _run_startup_delivery_background
        delivery_thread = threading.Thread(
            target=_run_startup_delivery_background,
            name="startup-delivery",
            daemon=True,
        )
        delivery_thread.start()
        _logger.info("Startup delivery: background thread launched")
    except Exception as exc:
        _logger.warning("Startup delivery failed to launch: %s", exc)

    yield


app = FastAPI(
    title="CrewAI Product Feature Planner API",
    version="0.1.0",
    description="HTTP interface for triggering CrewAI flows.",
    lifespan=_lifespan,
    openapi_tags=[
        {
            "name": "Health",
            "description": "Service liveness and readiness checks.",
        },
        {
            "name": "Flow Runs",
            "description": (
                "Start flows, list runs, query status, list resumable runs, "
                "and resume paused/unfinalized flows."
            ),
        },
        {
            "name": "Approvals",
            "description": (
                "Approve, refine, provide feedback, or pause PRD section "
                "refinement cycles."
            ),
        },
        {
            "name": "Jobs",
            "description": (
                "Persistent job records from the crewJobs MongoDB collection. "
                "Track flow run lifecycle, queue time, and running time."
            ),
        },
        {
            "name": "Slack Messenger",
            "description": (
                "Interact with the PRD Planner through Slack. "
                "Post a product idea and the bot will generate a full PRD. "
                "Supports ``webhook_url`` for push-based result delivery."
            ),
        },
        {
            "name": "Slack Events",
            "description": (
                "Handles inbound Slack Events API callbacks. "
                "Responds to bot channel joins with an intro message and "
                "processes @mentions and thread replies via OpenAI interpretation."
            ),
        },
        {
            "name": "Slack OAuth",
            "description": (
                "Handles the Slack OAuth v2 install/reinstall callback. "
                "Exchanges the authorization code for bot tokens and persists "
                "them to ``.env`` and ``.slack_tokens.json``."
            ),
        },
    ],
)

app.include_router(health_router)
app.include_router(prd_router)
app.include_router(slack_router)
app.include_router(slack_events_router)
app.include_router(slack_oauth_router)


# ── Global exception handler ─────────────────────────────────


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Return a structured ErrorResponse for any unhandled server error.

    This ensures every API endpoint returns a consistent JSON envelope
    (``ErrorResponse``) instead of a bare 500 HTML page, making errors
    machine-readable for MCP clients and dashboards.
    """
    from crewai_productfeature_planner.scripts.retry import BillingError, LLMError

    if isinstance(exc, BillingError):
        status_code = 503
        error_code = "BILLING_ERROR"
    elif isinstance(exc, LLMError):
        status_code = 503
        error_code = "LLM_ERROR"
    else:
        status_code = 500
        error_code = "INTERNAL_ERROR"

    _logger.error("Unhandled %s in %s %s: %s",
                  error_code, request.method, request.url.path, exc)

    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": error_code,
            "message": str(exc),
            "run_id": None,
            "detail": f"{type(exc).__name__}: {exc}",
        },
    )
