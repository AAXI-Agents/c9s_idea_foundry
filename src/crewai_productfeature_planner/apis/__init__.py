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
from crewai_productfeature_planner.mongodb.crew_jobs import fail_incomplete_jobs_on_startup
from crewai_productfeature_planner.scripts.logging_config import get_logger

_logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(application: FastAPI):
    """Startup / shutdown lifecycle hook.

    On startup, marks any incomplete jobs from previous runs as failed
    so they are not left in a stale ``queued`` / ``running`` state.
    """
    try:
        count = fail_incomplete_jobs_on_startup()
        if count:
            _logger.info("Startup recovery: %d incomplete job(s) marked as failed", count)
    except Exception as exc:
        _logger.warning("Startup recovery failed: %s", exc)
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
    ],
)

app.include_router(health_router)
app.include_router(prd_router)


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
