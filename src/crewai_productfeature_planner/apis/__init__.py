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

from fastapi import FastAPI

from crewai_productfeature_planner.apis.health.router import router as health_router
from crewai_productfeature_planner.apis.prd.router import router as prd_router
from crewai_productfeature_planner.apis.shared import FlowRun, FlowStatus  # noqa: F401 (re-export)

app = FastAPI(
    title="CrewAI Product Feature Planner API",
    version="0.1.0",
    description="HTTP interface for triggering CrewAI flows.",
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
    ],
)

app.include_router(health_router)
app.include_router(prd_router)
